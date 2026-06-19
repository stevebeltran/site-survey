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


class TestGmailServiceIntegration:
    """Test that gmail_lookup uses OAuth credentials."""

    @patch("gmail_lookup.google_oauth")
    @patch("gmail_lookup.build")
    def test_get_gmail_service_uses_oauth(self, mock_build, mock_oauth):
        from gmail_lookup import _get_gmail_service
        mock_creds = MagicMock()
        mock_oauth.get_credentials.return_value = mock_creds
        mock_build.return_value = MagicMock()
        result = _get_gmail_service()
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
        assert result is not None

    @patch("gmail_lookup.google_oauth")
    def test_get_gmail_service_returns_none_when_not_authenticated(self, mock_oauth):
        from gmail_lookup import _get_gmail_service
        mock_oauth.get_credentials.return_value = None
        result = _get_gmail_service()
        assert result is None


class TestDriveManagerOAuth:
    """Test that GoogleDriveManager accepts OAuth credentials."""

    @patch("google_drive.build")
    def test_init_with_credentials_object(self, mock_build):
        from google_drive import GoogleDriveManager
        from unittest.mock import MagicMock
        mock_creds = MagicMock()
        mock_build.return_value = MagicMock()
        manager = GoogleDriveManager(mock_creds)
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)
        assert manager.service is not None

    @patch("google_drive.build")
    def test_init_with_json_string_still_works(self, mock_build):
        from google_drive import GoogleDriveManager
        from unittest.mock import patch as inner_patch
        mock_build.return_value = MagicMock()
        fake_creds_json = '{"type":"service_account","project_id":"test","private_key_id":"x","private_key":"-----BEGIN RSA PRIVATE KEY-----\\nMIIBogIBAAJBALRiMLaH\\n-----END RSA PRIVATE KEY-----\\n","client_email":"test@test.iam.gserviceaccount.com","client_id":"123","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}'
        with inner_patch("google_drive.service_account.Credentials.from_service_account_info") as mock_sa:
            mock_sa.return_value = MagicMock()
            manager = GoogleDriveManager(fake_creds_json)
            mock_sa.assert_called_once()
