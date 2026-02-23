"""
Unit tests for JWT authentication middleware.

Tests JWT token creation, validation, expiry handling, and FastAPI dependencies.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

# Set required environment variables before imports
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_unit_tests_only")


class TestJWTMiddleware:
    """Tests for JWT token operations."""

    def test_create_jwt_token(self):
        """Test JWT token creation with valid email."""
        from src.auth.middleware import create_jwt_token, decode_jwt_token
        
        email = "test@example.com"
        token = create_jwt_token(email)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify
        decoded_email = decode_jwt_token(token)
        assert decoded_email == email

    def test_decode_valid_token(self):
        """Test decoding a valid JWT token."""
        from src.auth.middleware import create_jwt_token, decode_jwt_token
        
        email = "user@gmail.com"
        token = create_jwt_token(email)
        
        result = decode_jwt_token(token)
        assert result == email

    def test_decode_invalid_token(self):
        """Test that invalid tokens return None."""
        from src.auth.middleware import decode_jwt_token
        
        result = decode_jwt_token("invalid.token.here")
        assert result is None

    def test_decode_expired_token(self):
        """Test that expired tokens return None."""
        import jwt
        from src.auth.middleware import decode_jwt_token, get_jwt_secret, JWT_ALGORITHM
        
        # Create an already-expired token
        payload = {
            "sub": "expired@example.com",
            "iat": datetime.now(timezone.utc) - timedelta(days=10),
            "exp": datetime.now(timezone.utc) - timedelta(days=1),  # Expired yesterday
        }
        expired_token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
        
        result = decode_jwt_token(expired_token)
        assert result is None

    def test_decode_token_missing_subject(self):
        """Test handling token without subject claim."""
        import jwt
        from src.auth.middleware import decode_jwt_token, get_jwt_secret, JWT_ALGORITHM
        
        # Create token without 'sub' claim
        payload = {
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        }
        token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
        
        result = decode_jwt_token(token)
        assert result is None

    def test_get_jwt_secret_missing_raises(self):
        """Test that missing JWT_SECRET raises ValueError."""
        from src.auth.middleware import get_jwt_secret
        
        with patch.dict(os.environ, {}, clear=True):
            # Remove JWT_SECRET
            os.environ.pop("JWT_SECRET", None)
            
            with pytest.raises(ValueError) as exc_info:
                get_jwt_secret()
            
            assert "JWT_SECRET" in str(exc_info.value)


class TestAuthDependencies:
    """Tests for FastAPI authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_cookie(self):
        """Test get_current_user returns user when valid cookie present."""
        from src.auth.middleware import get_current_user, create_jwt_token, JWT_COOKIE_NAME
        
        email = "valid@example.com"
        token = create_jwt_token(email)
        
        # Mock request with cookie
        mock_request = MagicMock()
        mock_request.cookies = {JWT_COOKIE_NAME: token}
        
        user = await get_current_user(mock_request)
        
        assert user is not None
        assert user.email == email

    @pytest.mark.asyncio
    async def test_get_current_user_without_cookie(self):
        """Test get_current_user returns None when no cookie."""
        from src.auth.middleware import get_current_user
        
        mock_request = MagicMock()
        mock_request.cookies = {}
        
        user = await get_current_user(mock_request)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_cookie(self):
        """Test get_current_user returns None for invalid cookie."""
        from src.auth.middleware import get_current_user, JWT_COOKIE_NAME
        
        mock_request = MagicMock()
        mock_request.cookies = {JWT_COOKIE_NAME: "invalid.token"}
        
        user = await get_current_user(mock_request)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_require_auth_with_user(self):
        """Test require_auth passes through authenticated user."""
        from src.auth.middleware import require_auth, AuthenticatedUser
        
        user = AuthenticatedUser(email="auth@example.com")
        
        result = await require_auth(user)
        
        assert result == user

    @pytest.mark.asyncio
    async def test_require_auth_without_user_raises_401(self):
        """Test require_auth raises 401 when no user."""
        from src.auth.middleware import require_auth
        
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(None)
        
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail


class TestCookieHelpers:
    """Tests for cookie setting/clearing helpers."""

    def test_set_auth_cookie(self):
        """Test setting auth cookie on response."""
        from src.auth.middleware import set_auth_cookie, JWT_COOKIE_NAME
        
        mock_response = MagicMock()
        token = "test_token_value"
        
        set_auth_cookie(mock_response, token)
        
        mock_response.set_cookie.assert_called_once()
        call_kwargs = mock_response.set_cookie.call_args[1]
        
        assert call_kwargs["key"] == JWT_COOKIE_NAME
        assert call_kwargs["value"] == token
        assert call_kwargs["httponly"] is True
        assert call_kwargs["samesite"] == "lax"

    def test_clear_auth_cookie(self):
        """Test clearing auth cookie from response."""
        from src.auth.middleware import clear_auth_cookie, JWT_COOKIE_NAME
        
        mock_response = MagicMock()
        
        clear_auth_cookie(mock_response)
        
        # Called twice: once for the main cookie, once for stale domain=localhost
        assert mock_response.delete_cookie.call_count == 2
        first_call = mock_response.delete_cookie.call_args_list[0]
        assert first_call[1]["key"] == JWT_COOKIE_NAME
