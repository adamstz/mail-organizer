"""JWT authentication middleware for FastAPI.

Provides authentication dependencies that can be used to protect API endpoints.
Uses HTTP-only cookies for JWT storage for security.
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

import jwt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7
JWT_COOKIE_NAME = "auth_token"


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user."""
    email: str


def get_jwt_secret() -> str:
    """Get the JWT secret key from environment.

    Raises:
        ValueError: If JWT_SECRET is not set
    """
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise ValueError(
            "JWT_SECRET environment variable is required. "
            "Generate a secure random string (e.g., openssl rand -hex 32)"
        )
    return secret


def create_jwt_token(email: str) -> str:
    """Create a JWT token for a user.

    Args:
        email: The user's email address (identity)

    Returns:
        Signed JWT token string
    """
    secret = get_jwt_secret()

    payload = {
        "sub": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }

    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[str]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        User email if valid, None otherwise
    """
    try:
        secret = get_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        logger.debug("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid JWT token: {e}")
        return None


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the authentication cookie on a response.

    Args:
        response: FastAPI Response object
        token: JWT token to set
    """
    # Use secure settings appropriate for self-hosted
    # In production behind HTTPS, set secure=True
    is_secure = os.environ.get("SECURE_COOKIES", "false").lower() == "true"

    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,  # Prevent JavaScript access
        secure=is_secure,  # Only send over HTTPS if enabled
        samesite="lax",  # CSRF protection
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,  # Seconds
        path="/",
        domain="localhost",  # Share cookie across ports (5173 and 8000)
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie.

    Args:
        response: FastAPI Response object
    """
    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/",
        domain="localhost",  # Must match domain used in set_auth_cookie
    )


async def get_current_user(request: Request) -> Optional[AuthenticatedUser]:
    """Get the current authenticated user from the request.

    This is a FastAPI dependency that extracts and validates the JWT
    from the auth cookie. Returns None if not authenticated.

    Args:
        request: FastAPI Request object

    Returns:
        AuthenticatedUser if valid token present, None otherwise
    """
    token = request.cookies.get(JWT_COOKIE_NAME)

    if not token:
        return None

    email = decode_jwt_token(token)

    if not email:
        return None

    return AuthenticatedUser(email=email)


async def require_auth(
    user: Optional[AuthenticatedUser] = Depends(get_current_user)
) -> AuthenticatedUser:
    """Require authentication for an endpoint.

    Use this as a FastAPI dependency to protect endpoints.
    Raises 401 Unauthorized if not authenticated.

    Args:
        user: Injected by get_current_user dependency

    Returns:
        AuthenticatedUser

    Raises:
        HTTPException: 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please log in.",
        )
    return user
