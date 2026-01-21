"""Tests for OAuth token checking before requesting access."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request
from fastapi.responses import RedirectResponse

from src.auth.oauth import OAuthTokens, refresh_access_token
from src.auth.middleware import create_jwt_token, AuthenticatedUser

# Configure pytest to use anyio for async tests
pytestmark = pytest.mark.anyio


class TestOAuthTokenCheck:
    """Test OAuth flow checks for existing tokens before redirecting to Google."""

    @pytest.fixture
    def mock_storage(self):
        """Mock storage backend."""
        with patch('src.api.storage') as mock:
            yield mock

    @pytest.fixture
    def mock_get_current_user(self):
        """Mock get_current_user dependency."""
        with patch('src.api.get_current_user') as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_login_with_valid_jwt_session(self, mock_storage, mock_get_current_user):
        """Test that user with valid JWT session is redirected without OAuth."""
        from src.api import auth_login
        
        # Setup: user already has valid JWT session
        mock_user = AuthenticatedUser(email="test@example.com")
        mock_get_current_user.return_value = mock_user
        
        # Execute
        response = await auth_login(redirect_url=None, user=mock_user)
        
        # Verify: should redirect to frontend without OAuth
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" not in response.headers["location"]
        
        # Should not check storage since JWT is valid
        mock_storage.get_authenticated_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_with_valid_stored_tokens(self, mock_storage, mock_get_current_user):
        """Test that valid stored tokens create JWT session without OAuth."""
        from src.api import auth_login
        
        # Setup: no JWT session, but valid tokens in DB
        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        
        # Valid token that expires in the future
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "valid_access_token",
            "refresh_token": "refresh_token",
            "token_expiry": future_expiry
        }
        
        # Execute
        with patch('src.api.create_jwt_token') as mock_create_jwt:
            mock_create_jwt.return_value = "new_jwt_token"
            response = await auth_login(redirect_url=None, user=None)
        
        # Verify: should create JWT and redirect without OAuth
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" not in response.headers["location"]
        mock_create_jwt.assert_called_once_with("test@example.com")
        
        # Should not refresh token since it's still valid
        mock_storage.update_access_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_with_expired_tokens_successful_refresh(self, mock_storage, mock_get_current_user):
        """Test that expired tokens are refreshed successfully."""
        from src.api import auth_login
        
        # Setup: no JWT session, expired tokens in DB
        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        
        # Expired token
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "expired_access_token",
            "refresh_token": "refresh_token",
            "token_expiry": past_expiry
        }
        
        # Mock successful token refresh
        new_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch('src.auth.oauth.refresh_access_token') as mock_refresh, \
             patch('src.api.create_jwt_token') as mock_create_jwt, \
             patch('src.api.set_auth_cookie') as mock_set_cookie:
            
            mock_refresh.return_value = ("new_access_token", new_expiry)
            mock_create_jwt.return_value = "new_jwt_token"
            
            # Execute
            response = await auth_login(redirect_url=None, user=None)
        
        # Verify: should refresh token, update storage, and create JWT
        mock_refresh.assert_called_once_with("refresh_token")
        mock_storage.update_access_token.assert_called_once_with(
            email="test@example.com",
            access_token="new_access_token",
            token_expiry=new_expiry
        )
        mock_create_jwt.assert_called_once_with("test@example.com")
        
        # Should redirect without OAuth
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" not in response.headers["location"]

    @pytest.mark.asyncio
    async def test_login_with_expired_tokens_failed_refresh(self, mock_storage, mock_get_current_user):
        """Test that failed token refresh falls back to full OAuth."""
        from src.api import auth_login
        
        # Setup: no JWT session, expired tokens in DB
        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        
        # Expired token
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "expired_access_token",
            "refresh_token": "invalid_refresh_token",
            "token_expiry": past_expiry
        }
        
        # Mock failed token refresh
        with patch('src.auth.oauth.refresh_access_token') as mock_refresh, \
             patch('src.auth.oauth.get_google_auth_url') as mock_auth_url:
            
            mock_refresh.side_effect = ValueError("Invalid refresh token")
            mock_auth_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?..."
            
            # Execute
            response = await auth_login(redirect_url=None, user=None)
        
        # Verify: should attempt refresh, fail, then redirect to OAuth
        mock_refresh.assert_called_once()
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_login_with_no_tokens(self, mock_storage, mock_get_current_user):
        """Test that no tokens initiates full OAuth flow."""
        from src.api import auth_login
        
        # Setup: no JWT session, no stored tokens
        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = None
        
        with patch('src.api.get_google_auth_url') as mock_auth_url:
            mock_auth_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?..."
            
            # Execute
            response = await auth_login(redirect_url=None, user=None)
        
        # Verify: should redirect to OAuth
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" in response.headers["location"]
        mock_storage.get_oauth_tokens.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_with_no_refresh_token(self, mock_storage, mock_get_current_user):
        """Test that expired token without refresh token triggers OAuth."""
        from src.api import auth_login
        
        # Setup: expired token, no refresh token
        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "expired_access_token",
            "refresh_token": None,  # No refresh token
            "token_expiry": past_expiry
        }
        
        with patch('src.api.get_google_auth_url') as mock_auth_url:
            mock_auth_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?..."
            
            # Execute
            response = await auth_login(redirect_url=None, user=None)
        
        # Verify: should redirect to OAuth without attempting refresh
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_login_preserves_redirect_url(self, mock_storage, mock_get_current_user):
        """Test that redirect_url is preserved through token check."""
        from src.api import auth_login
        
        # Setup: valid stored tokens
        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "valid_access_token",
            "refresh_token": "refresh_token",
            "token_expiry": future_expiry
        }
        
        custom_redirect = "http://localhost:5173/dashboard"
        
        # Execute
        with patch('src.api.create_jwt_token') as mock_create_jwt:
            mock_create_jwt.return_value = "new_jwt_token"
            response = await auth_login(redirect_url=custom_redirect, user=None)
        
        # Verify: should redirect to custom URL
        assert isinstance(response, RedirectResponse)
        assert response.headers["location"] == custom_redirect
