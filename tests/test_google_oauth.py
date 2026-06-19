import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock


class TestValidateDomain:
    """Test that only @brincdrones.com emails are accepted."""

    def test_valid_brincdrones_email(self):
        from google_oauth import _validate_domain
        assert _validate_domain("steven.beltran@brincdrones.com") is True

    def test_invalid_domain_rejected(self):
        from google_oauth import _validate_domain
        assert _validate_domain("user@gmail.com") is False

    def test_empty_email_rejected(self):
        from google_oauth import _validate_domain
        assert _validate_domain("") is False

    def test_none_email_rejected(self):
        from google_oauth import _validate_domain
        assert _validate_domain(None) is False

    def test_subdomain_rejected(self):
        from google_oauth import _validate_domain
        assert _validate_domain("user@sub.brincdrones.com") is False


class TestGetCredentials:
    """Test credential retrieval from session state."""

    @patch("google_oauth.st")
    def test_returns_none_when_no_session(self, mock_st):
        from google_oauth import get_credentials
        mock_st.session_state = {}
        assert get_credentials() is None

    @patch("google_oauth.st")
    @patch("google_oauth.Credentials")
    def test_returns_credentials_when_stored(self, mock_creds_cls, mock_st):
        from google_oauth import get_credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_cls.return_value = mock_creds
        mock_st.session_state = {
            "google_oauth_token": {
                "token": "access-token",
                "refresh_token": "refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["openid", "email"],
            }
        }
        result = get_credentials()
        assert result is not None

    @patch("google_oauth.st")
    @patch("google_oauth.Credentials")
    @patch("google_oauth.Request")
    def test_refreshes_expired_token(self, mock_request_cls, mock_creds_cls, mock_st):
        from google_oauth import get_credentials
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh-token"
        mock_creds_cls.return_value = mock_creds
        mock_st.session_state = {
            "google_oauth_token": {
                "token": "expired-token",
                "refresh_token": "refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["openid", "email"],
            }
        }
        get_credentials()
        mock_creds.refresh.assert_called_once()

    @patch("google_oauth.st")
    @patch("google_oauth.Credentials")
    @patch("google_oauth.Request")
    def test_clears_session_on_refresh_failure(self, mock_request_cls, mock_creds_cls, mock_st):
        from google_oauth import get_credentials
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh-token"
        mock_creds.refresh.side_effect = Exception("Token revoked")
        mock_creds_cls.return_value = mock_creds
        mock_st.session_state = {
            "google_oauth_token": {
                "token": "expired-token",
                "refresh_token": "refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["openid", "email"],
            }
        }
        result = get_credentials()
        assert result is None
        assert "google_oauth_token" not in mock_st.session_state


class TestGetUserEmail:
    """Test email retrieval from session state."""

    @patch("google_oauth.st")
    def test_returns_email_when_stored(self, mock_st):
        from google_oauth import get_user_email
        mock_st.session_state = {"google_oauth_email": "steven.beltran@brincdrones.com"}
        assert get_user_email() == "steven.beltran@brincdrones.com"

    @patch("google_oauth.st")
    def test_returns_none_when_not_stored(self, mock_st):
        from google_oauth import get_user_email
        mock_st.session_state = {}
        assert get_user_email() is None
