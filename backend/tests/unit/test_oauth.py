"""
Unit tests for OAuth flow handlers.

Tests Google OAuth URL generation, token exchange (mocked), and configuration.
"""
import os
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

# Set required environment variables before imports
os.environ.setdefault("GOOGLE_CLIENT_ID", "test_client_id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test_client_secret")


class TestOAuthConfig:
    """Tests for OAuth configuration handling."""

    def test_get_oauth_config_success(self):
        """Test getting OAuth config with valid env vars."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "my_client_id",
            "GOOGLE_CLIENT_SECRET": "my_client_secret",
            "OAUTH_REDIRECT_URI": "http://localhost:8000/callback",
        }):
            from src.auth.oauth import get_oauth_config
            
            client_id, client_secret, redirect_uri = get_oauth_config()
            
            assert client_id == "my_client_id"
            assert client_secret == "my_client_secret"
            assert redirect_uri == "http://localhost:8000/callback"

    def test_get_oauth_config_default_redirect(self):
        """Test OAuth config uses default redirect URI if not set."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "my_client_id",
            "GOOGLE_CLIENT_SECRET": "my_client_secret",
        }, clear=True):
            # Ensure OAUTH_REDIRECT_URI is not set
            os.environ.pop("OAUTH_REDIRECT_URI", None)
            
            from src.auth.oauth import get_oauth_config
            
            _, _, redirect_uri = get_oauth_config()
            
            assert redirect_uri == "http://localhost:8000/api/auth/callback"

    def test_get_oauth_config_missing_client_id_raises(self):
        """Test that missing GOOGLE_CLIENT_ID raises ValueError."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_SECRET": "my_client_secret",
        }, clear=True):
            os.environ.pop("GOOGLE_CLIENT_ID", None)
            
            from src.auth.oauth import get_oauth_config
            
            with pytest.raises(ValueError) as exc_info:
                get_oauth_config()
            
            assert "GOOGLE_CLIENT_ID" in str(exc_info.value)

    def test_get_oauth_config_missing_client_secret_raises(self):
        """Test that missing GOOGLE_CLIENT_SECRET raises ValueError."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "my_client_id",
        }, clear=True):
            os.environ.pop("GOOGLE_CLIENT_SECRET", None)
            
            from src.auth.oauth import get_oauth_config
            
            with pytest.raises(ValueError) as exc_info:
                get_oauth_config()
            
            assert "GOOGLE_CLIENT_SECRET" in str(exc_info.value)


class TestOAuthURLGeneration:
    """Tests for Google OAuth URL generation using SDK."""

    def test_get_google_auth_url_basic(self):
        """Test generating basic Google auth URL returns tuple."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import get_google_auth_url
            
            url, state = get_google_auth_url()
            
            # Should return tuple
            assert isinstance(url, str)
            assert isinstance(state, str)
            
            # URL should contain Google OAuth endpoint
            assert "accounts.google.com" in url
            assert "client_id=test_client_id" in url
            assert "response_type=code" in url
            assert "access_type=offline" in url
            assert "prompt=consent" in url

    def test_get_google_auth_url_with_state(self):
        """Test generating auth URL with custom state parameter."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import get_google_auth_url
            
            custom_state = "http://localhost:5173/dashboard"
            url, returned_state = get_google_auth_url(state=custom_state)
            
            # Should use the provided state
            assert custom_state in url or returned_state == custom_state

    def test_get_google_auth_url_includes_scopes(self):
        """Test that auth URL includes required Gmail scopes."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import get_google_auth_url
            
            url, _ = get_google_auth_url()
            
            # URL should include gmail scope
            assert "gmail" in url.lower()
            assert "userinfo" in url.lower()


class TestAllowedEmail:
    """Tests for email restriction functionality."""

    def test_get_allowed_email_when_set(self):
        """Test getting allowed email when environment variable is set."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL": "admin@example.com"}):
            from src.auth.oauth import get_allowed_email
            
            result = get_allowed_email()
            
            assert result == "admin@example.com"

    def test_get_allowed_email_when_not_set(self):
        """Test getting allowed email returns None when not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ALLOWED_EMAIL", None)
            
            from src.auth.oauth import get_allowed_email
            
            result = get_allowed_email()
            
            assert result is None


class TestTokenExchange:
    """Tests for OAuth token exchange using Google SDK."""

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self):
        """Test successful token exchange using Google SDK."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            from datetime import datetime, timedelta, timezone
            
            # Mock the Google SDK Credentials object
            mock_credentials = MagicMock()
            mock_credentials.token = "mock_access_token"
            mock_credentials.refresh_token = "mock_refresh_token"
            mock_credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_credentials.id_token = {"email": "user@gmail.com"}
            
            # Mock the Flow object
            mock_flow = MagicMock()
            mock_flow.fetch_token = MagicMock()
            mock_flow.credentials = mock_credentials
            
            with patch("src.auth.oauth._create_flow", return_value=mock_flow):
                credentials = await exchange_code_for_tokens("test_auth_code")
            
            assert credentials.token == "mock_access_token"
            assert credentials.refresh_token == "mock_refresh_token"
            assert credentials.id_token["email"] == "user@gmail.com"

    @pytest.mark.asyncio
    async def test_exchange_code_rejects_unauthorized_email(self):
        """Test that token exchange rejects emails not in allowed list."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
            "ALLOWED_EMAIL": "admin@example.com",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            from datetime import datetime, timedelta, timezone
            
            # Mock credentials with unauthorized email
            mock_credentials = MagicMock()
            mock_credentials.token = "mock_access_token"
            mock_credentials.refresh_token = "mock_refresh_token"
            mock_credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_credentials.id_token = {"email": "unauthorized@gmail.com"}
            
            mock_flow = MagicMock()
            mock_flow.fetch_token = MagicMock()
            mock_flow.credentials = mock_credentials
            
            with patch("src.auth.oauth._create_flow", return_value=mock_flow):
                with pytest.raises(ValueError) as exc_info:
                    await exchange_code_for_tokens("test_auth_code")
            
            assert "not authorized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_exchange_code_missing_refresh_token_raises(self):
        """Test that missing refresh token raises error."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            from datetime import datetime, timedelta, timezone
            
            # Mock credentials without refresh token
            mock_credentials = MagicMock()
            mock_credentials.token = "mock_access_token"
            mock_credentials.refresh_token = None  # Missing!
            mock_credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_credentials.id_token = {"email": "user@gmail.com"}
            
            mock_flow = MagicMock()
            mock_flow.fetch_token = MagicMock()
            mock_flow.credentials = mock_credentials
            
            with patch("src.auth.oauth._create_flow", return_value=mock_flow):
                with pytest.raises(ValueError) as exc_info:
                    await exchange_code_for_tokens("test_code")
            
            assert "refresh_token" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_exchange_code_handles_scope_mismatch_warning(self):
        """Test that token exchange gracefully handles scope mismatch warnings."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            from datetime import datetime, timedelta, timezone
            
            # Mock credentials with reduced scopes (Gmail not granted)
            mock_credentials = MagicMock()
            mock_credentials.token = "mock_access_token"
            mock_credentials.refresh_token = "mock_refresh_token"
            mock_credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_credentials.id_token = {"email": "user@gmail.com"}
            mock_credentials.scopes = [
                "openid",
                "https://www.googleapis.com/auth/userinfo.email"
                # Note: gmail.modify NOT granted
            ]
            
            # Mock Flow that raises Warning on fetch_token (simulates scope mismatch)
            mock_flow = MagicMock()
            mock_flow.credentials = mock_credentials
            
            def mock_fetch_token(code):
                # Simulate oauthlib raising a Warning for scope mismatch
                raise Warning("Scope has changed from 'A B C' to 'A B'")
            
            mock_flow.fetch_token = mock_fetch_token
            
            with patch("src.auth.oauth._create_flow", return_value=mock_flow):
                # Should not raise, should handle warning gracefully
                credentials = await exchange_code_for_tokens("test_auth_code")
            
            # Should still return valid credentials with whatever scopes were granted
            assert credentials.token == "mock_access_token"
            assert credentials.refresh_token == "mock_refresh_token"
            assert credentials.id_token["email"] == "user@gmail.com"


class TestCredentialsHelper:
    """Tests for Credentials helper functions."""

    def test_get_email_from_credentials(self):
        """Test extracting email from Credentials object."""
        from src.auth.oauth import get_email_from_credentials
        
        mock_credentials = MagicMock()
        mock_credentials.id_token = {"email": "test@example.com"}
        
        email = get_email_from_credentials(mock_credentials)
        
        assert email == "test@example.com"
    
    def test_get_email_from_credentials_no_id_token(self):
        """Test extracting email when no ID token present."""
        from src.auth.oauth import get_email_from_credentials
        
        mock_credentials = MagicMock()
        mock_credentials.id_token = None
        
        email = get_email_from_credentials(mock_credentials)
        
        assert email is None

