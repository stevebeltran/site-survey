"""Google OAuth 2.0 Authorization Code flow for Streamlit.

Handles the full OAuth lifecycle: building the auth URL, capturing the
callback via st.query_params, exchanging the code for tokens, validating
the user's domain, and storing/refreshing credentials in st.session_state.
"""

import json
import os
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import streamlit as st

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive",
]

ALLOWED_DOMAIN = "brincdrones.com"

# Session state keys
_TOKEN_KEY = "google_oauth_token"
_EMAIL_KEY = "google_oauth_email"

# Persistent token file (survives page reloads / app restarts)
_TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".streamlit", "oauth_token.json")


def _save_token_to_disk(token_data, email):
    """Persist token data and email to disk as JSON."""
    try:
        os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
        payload = dict(token_data)
        payload["email"] = email
        with open(_TOKEN_FILE, "w") as f:
            json.dump(payload, f)
    except Exception:
        pass  # Disk write failure is non-fatal


def _load_token_from_disk():
    """Load token data from disk into session state if session state is empty."""
    if st.session_state.get(_TOKEN_KEY):
        return  # Already populated
    try:
        with open(_TOKEN_FILE, "r") as f:
            payload = json.load(f)
        email = payload.pop("email", None)
        st.session_state[_TOKEN_KEY] = payload
        if email:
            st.session_state[_EMAIL_KEY] = email
    except Exception:
        pass  # File missing or corrupt — nothing to restore


def _delete_token_file():
    """Remove the persisted token file from disk."""
    try:
        os.remove(_TOKEN_FILE)
    except Exception:
        pass  # File already gone or inaccessible


# On module load, attempt to restore tokens from disk (first import only;
# get_credentials() also calls this so new sessions after F5 are covered).
_load_token_from_disk()


def _get_redirect_uri():
    """Return the OAuth redirect URI for the current environment.

    On Streamlit Cloud the Host header gives the public domain; locally
    it falls back to the GOOGLE_OAUTH_REDIRECT_URI secret.
    """
    try:
        host = st.context.headers.get("Host", "")
        if host and "localhost" not in host and "127.0.0.1" not in host:
            proto = st.context.headers.get("X-Forwarded-Proto", "https")
            return f"{proto}://{host}"
    except Exception:
        pass
    return st.secrets.get("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8501")


def _get_client_config():
    """Build the OAuth client config dict from Streamlit secrets."""
    return {
        "web": {
            "client_id": st.secrets["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": st.secrets["GOOGLE_OAUTH_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_get_redirect_uri()],
        }
    }


def _validate_domain(email):
    """Check that the email belongs to the allowed domain.

    Args:
        email: Email address string, or None.

    Returns:
        True if the email ends with @brincdrones.com, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False
    return email.lower().endswith(f"@{ALLOWED_DOMAIN}")


def get_auth_url():
    """Build the Google OAuth consent URL.

    Constructs the URL directly without PKCE (code_challenge), since
    st.session_state is lost during the full-page redirect to Google
    and back. PKCE is not required for confidential clients (web apps
    with a client_secret).

    Returns:
        Authorization URL string that the user should be redirected to.
    """
    params = {
        "client_id": st.secrets["GOOGLE_OAUTH_CLIENT_ID"],
        "redirect_uri": _get_redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "hd": ALLOWED_DOMAIN,
    }
    return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"


def handle_callback():
    """Check for an OAuth callback code in query params and exchange it.

    Should be called early in the Streamlit app, before any UI rendering.
    If a 'code' param is present, exchanges it for tokens, validates the
    user's email domain, stores credentials in session state, clears the
    query params, and triggers a rerun.

    If the domain is invalid, shows an error and clears the params.
    """
    params = st.query_params
    code = params.get("code")
    if not code:
        return

    try:
        flow = Flow.from_client_config(
            _get_client_config(),
            scopes=SCOPES,
            redirect_uri=_get_redirect_uri(),
        )
        # No PKCE — auth URL was built without code_challenge
        flow.code_verifier = None
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Extract email from ID token
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        id_info = id_token.verify_oauth2_token(
            creds.id_token,
            google_requests.Request(),
            st.secrets["GOOGLE_OAUTH_CLIENT_ID"],
        )
        user_email = id_info.get("email", "")

        if not _validate_domain(user_email):
            st.error(f"Access restricted to @{ALLOWED_DOMAIN} accounts. Got: {user_email}")
            st.query_params.clear()
            return

        # Store credentials and email in session state
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes),
        }
        st.session_state[_TOKEN_KEY] = token_data
        st.session_state[_EMAIL_KEY] = user_email
        _save_token_to_disk(token_data, user_email)

        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Google authentication failed: {e}")
        st.query_params.clear()


def get_credentials():
    """Return the current user's OAuth credentials, or None.

    If the access token is expired and a refresh token exists, silently
    refreshes. If refresh fails, clears stored credentials and returns None.

    Returns:
        google.oauth2.credentials.Credentials or None
    """
    # Restore tokens from disk on new sessions (F5 refresh etc.)
    _load_token_from_disk()

    token_data = st.session_state.get(_TOKEN_KEY)
    if not token_data:
        return None

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Update stored token with refreshed values
            st.session_state[_TOKEN_KEY]["token"] = creds.token
            _save_token_to_disk(st.session_state[_TOKEN_KEY],
                                st.session_state.get(_EMAIL_KEY, ""))
            return creds
        except Exception:
            # Refresh failed — clear everything
            st.session_state.pop(_TOKEN_KEY, None)
            st.session_state.pop(_EMAIL_KEY, None)
            _delete_token_file()
            return None

    # No refresh token and token invalid — clear
    st.session_state.pop(_TOKEN_KEY, None)
    st.session_state.pop(_EMAIL_KEY, None)
    _delete_token_file()
    return None


def get_user_email():
    """Return the authenticated user's email, or None."""
    _load_token_from_disk()
    return st.session_state.get(_EMAIL_KEY)


def render_connect_button(label="Connect Google Account"):
    """Render a link button to start the OAuth flow.

    Uses st.link_button so the redirect works reliably inside
    columns, tabs, and other Streamlit container contexts.

    Args:
        label: Button text to display.
    """
    try:
        auth_url = get_auth_url()
        st.link_button(f"🔗 {label}", auth_url, use_container_width=True)
    except Exception:
        st.warning("Google OAuth not configured. Add GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI to Streamlit secrets.")


def is_authenticated():
    """Return True if the user has valid OAuth credentials."""
    return get_credentials() is not None
