"""Tests for OAuth token checking before requesting access."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request
from fastapi.responses import RedirectResponse

from src.auth.oauth import refresh_access_token
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
        mock_storage.is_gmail_connected.return_value = {"connected": True}
        
        # Execute
        response = await auth_login(redirect_url=None, user=mock_user)
        
        # Verify: should redirect to frontend without OAuth
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" not in response.headers["location"]
        
        # Should verify Gmail connection status
        mock_storage.is_gmail_connected.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_login_no_jwt_has_refresh_token_uses_select_account(self, mock_storage, mock_get_current_user):
        """Test that no-JWT login uses select_account when an existing refresh token is in the DB.

        Returning users who still have a stored refresh token should see only the
        account-picker screen (not the full consent screen) to minimise friction.
        """
        from src.api import auth_login

        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "old_access",
            "refresh_token": "existing_refresh",
        }

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?prompt=select_account", "encoded_state")

            response = await auth_login(redirect_url=None, user=None)

        # Should redirect to Google OAuth with select_account
        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" in response.headers["location"]
        mock_auth_url.assert_called_once()
        _, call_kwargs = mock_auth_url.call_args
        assert call_kwargs.get("prompt") == "select_account"

    @pytest.mark.asyncio
    async def test_login_no_jwt_no_existing_user_uses_consent(self, mock_storage, mock_get_current_user):
        """Test that no-JWT login uses consent when no user exists in the DB (first login)."""
        from src.api import auth_login

        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = None

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?prompt=consent", "encoded_state")

            response = await auth_login(redirect_url=None, user=None)

        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" in response.headers["location"]
        mock_auth_url.assert_called_once()
        _, call_kwargs = mock_auth_url.call_args
        assert call_kwargs.get("prompt") == "consent"

    @pytest.mark.asyncio
    async def test_login_no_jwt_existing_user_no_refresh_token_uses_consent(
        self, mock_storage, mock_get_current_user
    ):
        """Test that no-JWT login uses consent when user exists but has no refresh token.

        This covers the case where the token was revoked or the DB row lost its refresh
        token — consent is needed to obtain a fresh one and break the auth loop.
        """
        from src.api import auth_login

        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        mock_storage.get_oauth_tokens.return_value = None  # No tokens in DB

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?prompt=consent", "encoded_state")

            response = await auth_login(redirect_url=None, user=None)

        assert isinstance(response, RedirectResponse)
        assert "accounts.google.com" in response.headers["location"]
        mock_auth_url.assert_called_once()
        _, call_kwargs = mock_auth_url.call_args
        assert call_kwargs.get("prompt") == "consent"

    @pytest.mark.asyncio
    async def test_login_force_uses_consent(self, mock_storage, mock_get_current_user):
        """Test that force=True always uses prompt=consent to get a fresh refresh token."""
        from src.api import auth_login

        mock_get_current_user.return_value = None

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?prompt=consent", "encoded_state")

            response = await auth_login(redirect_url=None, force=True, user=None)

        assert isinstance(response, RedirectResponse)
        mock_auth_url.assert_called_once()
        _, call_kwargs = mock_auth_url.call_args
        assert call_kwargs.get("prompt") == "consent"

    @pytest.mark.asyncio
    async def test_login_jwt_gmail_disconnected_has_db_tokens_uses_select_account(
        self, mock_storage, mock_get_current_user
    ):
        """Test JWT-valid but Gmail-disconnected uses select_account when DB token exists."""
        from src.api import auth_login

        mock_user = AuthenticatedUser(email="test@example.com")
        mock_get_current_user.return_value = mock_user
        mock_storage.is_gmail_connected.return_value = {"connected": False}
        mock_storage.get_oauth_tokens.return_value = {
            "access_token": "old_token",
            "refresh_token": "refresh_token",
        }

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?prompt=select_account", "encoded_state")

            response = await auth_login(redirect_url=None, user=mock_user)

        assert isinstance(response, RedirectResponse)
        mock_auth_url.assert_called_once()
        _, call_kwargs = mock_auth_url.call_args
        assert call_kwargs.get("prompt") == "select_account"

    @pytest.mark.asyncio
    async def test_login_jwt_gmail_disconnected_no_db_tokens_uses_consent(
        self, mock_storage, mock_get_current_user
    ):
        """Test JWT-valid but Gmail-disconnected uses consent when no DB token exists."""
        from src.api import auth_login

        mock_user = AuthenticatedUser(email="test@example.com")
        mock_get_current_user.return_value = mock_user
        mock_storage.is_gmail_connected.return_value = {"connected": False}
        mock_storage.get_oauth_tokens.return_value = None  # No tokens in DB

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?prompt=consent", "encoded_state")

            response = await auth_login(redirect_url=None, user=mock_user)

        assert isinstance(response, RedirectResponse)
        mock_auth_url.assert_called_once()
        _, call_kwargs = mock_auth_url.call_args
        assert call_kwargs.get("prompt") == "consent"

    @pytest.mark.asyncio
    async def test_login_no_jwt_encodes_redirect_url_in_state(self, mock_storage, mock_get_current_user):
        """Test that redirect_url is encoded into the OAuth state for later retrieval."""
        from src.api import auth_login

        mock_get_current_user.return_value = None
        mock_storage.get_authenticated_email.return_value = "test@example.com"
        mock_storage.get_oauth_tokens.return_value = {"refresh_token": "existing_refresh"}
        custom_redirect = "http://localhost:5173/dashboard"

        with patch('src.api.get_google_auth_url') as mock_auth_url, \
             patch('src.api.generate_oauth_state') as mock_state, \
             patch('src.api.set_oauth_state_cookie'):

            mock_state.return_value = ("encoded_state", "nonce123")
            mock_auth_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth", "encoded_state")

            response = await auth_login(redirect_url=custom_redirect, user=None)

        # The redirect_url must be passed to generate_oauth_state so it survives the OAuth round-trip
        mock_state.assert_called_once_with(custom_redirect)
        assert isinstance(response, RedirectResponse)
