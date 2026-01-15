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
    """Tests for Google OAuth URL generation."""

    def test_get_google_auth_url_basic(self):
        """Test generating basic Google auth URL."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import get_google_auth_url
            
            url = get_google_auth_url()
            
            assert "accounts.google.com" in url
            assert "client_id=test_client_id" in url
            assert "response_type=code" in url
            assert "access_type=offline" in url
            assert "prompt=consent" in url

    def test_get_google_auth_url_with_state(self):
        """Test generating auth URL with state parameter."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import get_google_auth_url
            
            state = "http://localhost:5173/dashboard"
            url = get_google_auth_url(state=state)
            
            assert f"state={state}" in url

    def test_get_google_auth_url_includes_scopes(self):
        """Test that auth URL includes required Gmail scopes."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import get_google_auth_url
            
            url = get_google_auth_url()
            
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
    """Tests for OAuth token exchange (with mocked HTTP calls)."""

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self):
        """Test successful token exchange."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            
            # Mock the httpx responses
            mock_token_response = MagicMock()
            mock_token_response.status_code = 200
            mock_token_response.json.return_value = {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_in": 3600,
            }
            
            mock_userinfo_response = MagicMock()
            mock_userinfo_response.status_code = 200
            mock_userinfo_response.json.return_value = {
                "email": "user@gmail.com",
            }
            
            # Create mock client
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_token_response
            mock_client.get.return_value = mock_userinfo_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            
            with patch("src.auth.oauth.httpx.AsyncClient", return_value=mock_client):
                tokens = await exchange_code_for_tokens("test_auth_code")
            
            assert tokens.access_token == "mock_access_token"
            assert tokens.refresh_token == "mock_refresh_token"
            assert tokens.email == "user@gmail.com"
            assert tokens.token_expiry is not None

    @pytest.mark.asyncio
    async def test_exchange_code_rejects_unauthorized_email(self):
        """Test that token exchange rejects emails not in allowed list."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
            "ALLOWED_EMAIL": "admin@example.com",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            
            # Mock responses - user email doesn't match allowed
            mock_token_response = MagicMock()
            mock_token_response.status_code = 200
            mock_token_response.json.return_value = {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_in": 3600,
            }
            
            mock_userinfo_response = MagicMock()
            mock_userinfo_response.status_code = 200
            mock_userinfo_response.json.return_value = {
                "email": "unauthorized@gmail.com",  # Different from ALLOWED_EMAIL
            }
            
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_token_response
            mock_client.get.return_value = mock_userinfo_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            
            with patch("src.auth.oauth.httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(ValueError) as exc_info:
                    await exchange_code_for_tokens("test_auth_code")
            
            assert "not authorized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_exchange_code_token_error(self):
        """Test handling of token exchange errors."""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test_client_id",
            "GOOGLE_CLIENT_SECRET": "test_secret",
        }):
            from src.auth.oauth import exchange_code_for_tokens
            
            # Mock failed token response
            mock_token_response = MagicMock()
            mock_token_response.status_code = 400
            mock_token_response.text = "invalid_grant"
            
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_token_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            
            with patch("src.auth.oauth.httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(ValueError) as exc_info:
                    await exchange_code_for_tokens("invalid_code")
            
            assert "Failed to exchange" in str(exc_info.value)


class TestOAuthTokens:
    """Tests for OAuthTokens dataclass."""

    def test_oauth_tokens_dataclass(self):
        """Test OAuthTokens dataclass creation."""
        from src.auth.oauth import OAuthTokens
        
        expiry = datetime.now(timezone.utc)
        tokens = OAuthTokens(
            access_token="access",
            refresh_token="refresh",
            token_expiry=expiry,
            email="test@example.com",
        )
        
        assert tokens.access_token == "access"
        assert tokens.refresh_token == "refresh"
        assert tokens.token_expiry == expiry
        assert tokens.email == "test@example.com"
