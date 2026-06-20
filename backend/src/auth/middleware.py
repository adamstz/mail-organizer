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
OAUTH_STATE_COOKIE_NAME = "oauth_state"
PKCE_VERIFIER_COOKIE_NAME = "pkce_verifier"


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

    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    logger.info(f"[Auth] Created JWT token for {email} (expires in {JWT_EXPIRY_DAYS} days)")
    return token


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
        email = payload.get("sub")
        logger.debug(f"[Auth] JWT decoded successfully — sub={email}")
        return email
    except jwt.ExpiredSignatureError:
        logger.debug("[Auth] JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"[Auth] Invalid JWT token: {e}")
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
    cookie_domain = os.environ.get("COOKIE_DOMAIN")  # Optional: set for multi-subdomain deployments

    kwargs: dict = dict(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,  # Prevent JavaScript access
        secure=is_secure,  # Only send over HTTPS if enabled
        samesite="lax",  # CSRF protection
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,  # Seconds
        path="/",
    )
    # Only set domain if explicitly configured; omitting lets the browser
    # scope the cookie to the exact origin host, which works for both
    # localhost dev and single-origin production deployments.
    if cookie_domain:
        kwargs["domain"] = cookie_domain

    response.set_cookie(**kwargs)
    logger.debug(f"[Auth] Set auth cookie (secure={is_secure}, domain={cookie_domain or 'auto'}, max_age={JWT_EXPIRY_DAYS}d)")


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie.

    Args:
        response: FastAPI Response object
    """
    cookie_domain = os.environ.get("COOKIE_DOMAIN")
    kwargs: dict = dict(
        key=JWT_COOKIE_NAME,
        path="/",
    )
    if cookie_domain:
        kwargs["domain"] = cookie_domain

    response.delete_cookie(**kwargs)
    logger.debug(f"[Auth] Cleared auth cookie (domain={cookie_domain or 'auto'})")

    # Also clear any stale cookie that was previously set with domain="localhost"
    # so that users who upgrade don't get stuck with an old cookie.
    if cookie_domain != "localhost":
        response.delete_cookie(
            key=JWT_COOKIE_NAME,
            path="/",
            domain="localhost",
        )


def set_oauth_state_cookie(response: Response, nonce: str) -> None:
    """Set the one-time OAuth CSRF state cookie.

    This cookie stores the nonce that must match the state parameter
    returned from Google in the OAuth callback.

    Args:
        response: FastAPI Response object
        nonce: Random nonce string
    """
    is_secure = os.environ.get("SECURE_COOKIES", "false").lower() == "true"
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=nonce,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=600,  # 10 minutes — OAuth flow should complete quickly
        path="/",
    )
    logger.debug(f"[Auth] Set OAuth state cookie (nonce={nonce[:8]}..., max_age=600s)")


def clear_oauth_state_cookie(response: Response) -> None:
    """Clear the OAuth CSRF state cookie after verification."""
    response.delete_cookie(key=OAUTH_STATE_COOKIE_NAME, path="/")
    logger.debug("[Auth] Cleared OAuth state cookie")


def set_pkce_cookie(response: Response, code_verifier: str) -> None:
    """Store the PKCE code_verifier in an httponly cookie for the OAuth flow."""
    is_secure = os.environ.get("SECURE_COOKIES", "false").lower() == "true"
    response.set_cookie(
        key=PKCE_VERIFIER_COOKIE_NAME,
        value=code_verifier,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=600,
        path="/",
    )
    logger.debug("[Auth] Set PKCE verifier cookie")


def clear_pkce_cookie(response: Response) -> None:
    """Clear the PKCE verifier cookie after token exchange."""
    response.delete_cookie(key=PKCE_VERIFIER_COOKIE_NAME, path="/")
    logger.debug("[Auth] Cleared PKCE verifier cookie")


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
        logger.debug("[Auth] No JWT cookie present in request")
        return None

    email = decode_jwt_token(token)

    if not email:
        logger.debug("[Auth] JWT cookie present but decode failed")
        return None

    logger.debug(f"[Auth] Authenticated user from JWT: {email}")
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
        logger.debug("[Auth] require_auth: no authenticated user — returning 401")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please log in.",
        )
    logger.debug(f"[Auth] require_auth: user {user.email} authorized")
    return user
