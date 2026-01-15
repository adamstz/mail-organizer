"""Google OAuth2 flow handlers.

Handles the OAuth2 authorization code flow for Gmail access:
1. Generate authorization URL for user consent
2. Exchange authorization code for tokens
3. Refresh expired access tokens
4. Extract user email from ID token
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Required scopes for Gmail access
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


@dataclass
class OAuthTokens:
    """Container for OAuth token data."""
    access_token: str
    refresh_token: str
    token_expiry: datetime
    email: str


def get_oauth_config() -> tuple[str, str, str]:
    """Get OAuth configuration from environment variables.
    
    Returns:
        Tuple of (client_id, client_secret, redirect_uri)
    
    Raises:
        ValueError: If required environment variables are not set
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.environ.get(
        "OAUTH_REDIRECT_URI",
        "http://localhost:8000/api/auth/callback"
    )
    
    if not client_id or not client_secret:
        raise ValueError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are required. "
            "Create OAuth credentials at https://console.cloud.google.com/apis/credentials"
        )
    
    return client_id, client_secret, redirect_uri


def get_allowed_email() -> Optional[str]:
    """Get the allowed email address for single-user restriction.
    
    Returns:
        Email address if ALLOWED_EMAIL is set, None otherwise
    """
    return os.environ.get("ALLOWED_EMAIL")


def get_google_auth_url(state: Optional[str] = None) -> str:
    """Generate the Google OAuth2 authorization URL.
    
    Args:
        state: Optional state parameter for CSRF protection
    
    Returns:
        URL to redirect user to for Google OAuth consent
    """
    client_id, _, redirect_uri = get_oauth_config()
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Force consent to ensure refresh token
    }
    
    if state:
        params["state"] = state
    
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query_string}"


async def exchange_code_for_tokens(code: str) -> OAuthTokens:
    """Exchange authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from OAuth callback
    
    Returns:
        OAuthTokens containing access_token, refresh_token, expiry, and email
    
    Raises:
        ValueError: If token exchange fails or user email doesn't match ALLOWED_EMAIL
    """
    client_id, client_secret, redirect_uri = get_oauth_config()
    
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        
        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            raise ValueError(f"Failed to exchange code for tokens: {token_response.text}")
        
        token_data = token_response.json()
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        
        if not access_token or not refresh_token:
            raise ValueError("Token response missing access_token or refresh_token")
        
        # Calculate token expiry
        token_expiry = datetime.now(timezone.utc).timestamp() + expires_in
        expiry_dt = datetime.fromtimestamp(token_expiry, tz=timezone.utc)
        
        # Get user email from userinfo endpoint
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        if userinfo_response.status_code != 200:
            raise ValueError("Failed to get user info from Google")
        
        userinfo = userinfo_response.json()
        email = userinfo.get("email")
        
        if not email:
            raise ValueError("Could not get email from Google userinfo")
        
        # Check if email is allowed (if restriction is set)
        allowed_email = get_allowed_email()
        if allowed_email and email.lower() != allowed_email.lower():
            logger.warning(f"Rejected OAuth for email {email} (allowed: {allowed_email})")
            raise ValueError(f"Email {email} is not authorized. Only {allowed_email} is allowed.")
        
        logger.info(f"Successfully exchanged code for tokens for user: {email}")
        
        return OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=expiry_dt,
            email=email,
        )


async def refresh_access_token(refresh_token: str) -> tuple[str, datetime]:
    """Refresh an expired access token.
    
    Args:
        refresh_token: The refresh token to use
    
    Returns:
        Tuple of (new_access_token, new_expiry_datetime)
    
    Raises:
        ValueError: If token refresh fails
    """
    client_id, client_secret, _ = get_oauth_config()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        
        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.text}")
            raise ValueError(f"Failed to refresh token: {response.text}")
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        
        if not access_token:
            raise ValueError("Token refresh response missing access_token")
        
        token_expiry = datetime.now(timezone.utc).timestamp() + expires_in
        expiry_dt = datetime.fromtimestamp(token_expiry, tz=timezone.utc)
        
        return access_token, expiry_dt


async def get_user_email_from_token(access_token: str) -> str:
    """Get the user's email address from an access token.
    
    Args:
        access_token: Valid Google access token
    
    Returns:
        User's email address
    
    Raises:
        ValueError: If unable to get user info
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        if response.status_code != 200:
            raise ValueError("Failed to get user info from Google")
        
        userinfo = response.json()
        email = userinfo.get("email")
        
        if not email:
            raise ValueError("Could not get email from Google userinfo")
        
        return email
