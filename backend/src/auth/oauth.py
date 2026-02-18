"""Google OAuth2 flow handlers using Google's official SDK.

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
from datetime import datetime, timezone

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)

# Required scopes for Gmail access
# Using gmail.modify for read, modify, and delete (not send)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def get_backend_url() -> str:
    """Get the backend base URL from environment or default to localhost."""
    return os.environ.get("BACKEND_URL", "http://localhost:8000")


def get_oauth_config() -> tuple[str, str, str]:
    """Get OAuth configuration from environment variables.

    Returns:
        Tuple of (client_id, client_secret, redirect_uri)

    Raises:
        ValueError: If required environment variables are not set
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    # Build redirect URI from BACKEND_URL if OAUTH_REDIRECT_URI not explicitly set
    default_redirect = f"{get_backend_url()}/api/auth/callback"
    redirect_uri = os.environ.get("OAUTH_REDIRECT_URI", default_redirect)

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


def _create_flow(state: Optional[str] = None) -> Flow:
    """Create a Google OAuth Flow instance.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Configured Flow instance
    """
    client_id, client_secret, redirect_uri = get_oauth_config()

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )

    return flow


def get_google_auth_url(state: Optional[str] = None) -> tuple[str, str]:
    """Generate the Google OAuth2 authorization URL using Google SDK.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Tuple of (authorization_url, state)
        If state was provided, returns the same state. Otherwise returns SDK-generated state.
    """
    flow = _create_flow(state=state)

    auth_url, returned_state = flow.authorization_url(
        access_type="offline",  # Request refresh token
        prompt="consent",  # Force consent to ensure refresh token
        include_granted_scopes="true",
    )

    logger.info(f"Generated OAuth URL using Google SDK")
    return auth_url, returned_state


async def exchange_code_for_tokens(code: str, state: Optional[str] = None) -> Credentials:
    """Exchange authorization code for access and refresh tokens using Google SDK.

    Args:
        code: Authorization code from OAuth callback
        state: Optional state parameter for CSRF verification

    Returns:
        google.oauth2.credentials.Credentials object containing tokens and user info

    Raises:
        ValueError: If token exchange fails or user email doesn't match ALLOWED_EMAIL
        RefreshError: If the OAuth flow fails
    """
    try:
        flow = _create_flow(state=state)

        # Exchange authorization code for tokens
        # oauthlib may raise Warning exception if returned scopes differ from requested
        try:
            flow.fetch_token(code=code)
        except Warning as w:
            # This is expected when Google grants fewer scopes than requested
            # The credentials are still populated, so we can continue
            logger.warning(f"Scope mismatch during token exchange (this is expected): {w}")

        credentials = flow.credentials

        # Verify we got credentials despite potential scope mismatch
        if not credentials:
            raise ValueError("Failed to obtain credentials from OAuth flow")

        if not credentials.refresh_token:
            raise ValueError("Token response missing refresh_token. Ensure prompt=consent is set.")

        # Extract email from ID token
        # The ID token might be a JWT string that needs to be decoded
        raw_id_token = credentials.id_token
        if not raw_id_token:
            logger.error(f"Credentials object has no id_token")
            raise ValueError("Could not get ID token from credentials")

        # Decode the ID token if it's a string (JWT)
        if isinstance(raw_id_token, str):
            try:
                client_id, _, _ = get_oauth_config()
                id_token_claims = google_id_token.verify_oauth2_token(
                    raw_id_token,
                    google_requests.Request(),
                    client_id
                )
            except Exception as e:
                logger.error(f"Failed to verify ID token: {e}")
                raise ValueError(f"Failed to decode ID token: {e}")
        else:
            # Already a dict
            id_token_claims = raw_id_token

        if "email" not in id_token_claims:
            logger.error(f"ID token missing email claim. Claims: {id_token_claims.keys()}")
            raise ValueError("ID token does not contain email claim")

        email = id_token_claims["email"]

        # Check if email is allowed (if restriction is set)
        allowed_email = get_allowed_email()
        if allowed_email and email.lower() != allowed_email.lower():
            logger.warning(f"Rejected OAuth for email {email} (allowed: {allowed_email})")
            raise ValueError(f"Email {email} is not authorized. Only {allowed_email} is allowed.")

        # Log what scopes were actually granted
        granted_scopes = credentials.scopes or []
        logger.info(f"Successfully exchanged code for tokens for user: {email}, granted scopes: {granted_scopes}")
        return credentials

    except RefreshError as e:
        logger.error(f"Token exchange failed: {e}")
        raise ValueError(f"Failed to exchange code for tokens: {e}") from e
    except ValueError:
        # Re-raise ValueError as-is (from our own validation above)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {e}")
        raise


async def refresh_access_token(refresh_token_str: str) -> tuple[str, datetime]:
    """Refresh an expired access token using Google SDK.

    Args:
        refresh_token_str: The refresh token to use

    Returns:
        Tuple of (new_access_token, new_expiry_datetime)

    Raises:
        ValueError: If token refresh fails
        RefreshError: If the refresh operation fails
    """
    try:
        client_id, client_secret, _ = get_oauth_config()

        # Create a Credentials object from the refresh token
        credentials = Credentials(
            token=None,  # No access token yet
            refresh_token=refresh_token_str,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=GMAIL_SCOPES,
        )

        # Refresh the credentials
        request = Request()
        credentials.refresh(request)

        if not credentials.token:
            raise ValueError("Token refresh response missing access_token")

        # Get expiry datetime (SDK provides this directly)
        expiry_dt = credentials.expiry or datetime.now(timezone.utc)

        logger.info("Successfully refreshed access token")
        return credentials.token, expiry_dt

    except RefreshError as e:
        logger.error(f"Token refresh failed: {e}")
        raise ValueError(f"Failed to refresh token: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        raise


def get_email_from_credentials(credentials: Credentials) -> Optional[str]:
    """Extract email from Credentials ID token.

    Args:
        credentials: Google OAuth2 Credentials object

    Returns:
        User's email address if available in ID token, None otherwise
    """
    if not credentials.id_token:
        return None

    # Handle both JWT string and dict formats
    if isinstance(credentials.id_token, str):
        try:
            client_id, _, _ = get_oauth_config()
            id_token_claims = google_id_token.verify_oauth2_token(
                credentials.id_token,
                google_requests.Request(),
                client_id
            )
            return id_token_claims.get("email")
        except Exception as e:
            logger.debug(f"Failed to decode ID token: {e}")
            return None
    else:
        # Already a dict
        return credentials.id_token.get("email")

