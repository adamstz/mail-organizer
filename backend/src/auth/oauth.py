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
import secrets
import json
import base64
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
    logger.debug("[OAuth] Loading OAuth config from environment variables")
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    # Build redirect URI from BACKEND_URL if OAUTH_REDIRECT_URI not explicitly set
    default_redirect = f"{get_backend_url()}/api/auth/callback"
    redirect_uri = os.environ.get("OAUTH_REDIRECT_URI", default_redirect)

    if not client_id or not client_secret:
        logger.error("[OAuth] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")
        raise ValueError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are required. "
            "Create OAuth credentials at https://console.cloud.google.com/apis/credentials"
        )

    logger.debug(f"[OAuth] Config loaded — client_id={client_id[:8]}..., redirect_uri={redirect_uri}")
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
    logger.debug(f"[OAuth] Creating Google OAuth Flow (state={'set' if state else 'none'})")
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

    logger.debug(f"[OAuth] Flow created with redirect_uri={redirect_uri}, scopes={GMAIL_SCOPES}")
    return flow


def get_google_auth_url(state: Optional[str] = None, prompt: str = "consent") -> tuple[str, str]:
    """Generate the Google OAuth2 authorization URL using Google SDK.

    Args:
        state: Optional state parameter for CSRF protection
        prompt: OAuth prompt parameter. Use "consent" to force the consent screen and
            guarantee a refresh token is returned. Use "select_account" when a refresh
            token already exists in the DB — Google will show an account picker but
            skip the full consent screen.

    Returns:
        Tuple of (authorization_url, state)
        If state was provided, returns the same state. Otherwise returns SDK-generated state.
    """
    logger.info(f"[OAuth] Generating Google auth URL (state={'provided' if state else 'auto'}, prompt={prompt})")
    flow = _create_flow(state=state)

    auth_url, returned_state = flow.authorization_url(
        access_type="offline",  # Request refresh token
        prompt=prompt,
        include_granted_scopes="true",
    )

    logger.info(f"[OAuth] Generated auth URL (access_type=offline, prompt={prompt})")
    logger.debug(f"[OAuth] Auth URL domain: {auth_url.split('?')[0]}")
    return auth_url, returned_state


def generate_oauth_state(redirect_url: Optional[str] = None) -> tuple[str, str]:
    """Generate a CSRF-protected OAuth state parameter.

    Encodes a random nonce and optional redirect URL into a base64 JSON string.
    The nonce should be stored in an httponly cookie and verified on callback.

    Args:
        redirect_url: Optional URL to redirect to after successful auth

    Returns:
        Tuple of (state_param_for_google, nonce_for_cookie)
    """
    nonce = secrets.token_urlsafe(32)
    payload: dict = {"nonce": nonce}
    if redirect_url:
        payload["redirect_url"] = redirect_url
    state = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    logger.debug(
        f"[OAuth] Generated CSRF state (redirect_url={'set: ' + redirect_url if redirect_url else 'none'}, "
        f"nonce={nonce[:8]}...)"
    )
    return state, nonce


def verify_oauth_state(state: str, expected_nonce: str) -> tuple[bool, Optional[str]]:
    """Verify the CSRF nonce in the OAuth state and extract the redirect URL.

    Args:
        state: The state parameter returned from Google (base64 JSON)
        expected_nonce: The nonce stored in the httponly cookie

    Returns:
        Tuple of (is_valid, redirect_url). redirect_url may be None.
    """
    logger.debug(f"[OAuth] Verifying CSRF state (expected_nonce={expected_nonce[:8]}...)")
    try:
        payload = json.loads(base64.urlsafe_b64decode(state))
        nonce = payload.get("nonce", "")
        if not secrets.compare_digest(nonce, expected_nonce):
            logger.warning("[OAuth] CSRF state nonce mismatch")
            return False, None
        redirect_url = payload.get("redirect_url")
        logger.info(f"[OAuth] CSRF state verified successfully (redirect_url={redirect_url or 'none'})")
        return True, redirect_url
    except Exception as e:
        logger.warning(f"[OAuth] Failed to decode OAuth state: {e}")
        return False, None


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
    logger.info(f"[OAuth] Starting token exchange (code={code[:8]}..., state={'set' if state else 'none'})")
    try:
        flow = _create_flow(state=state)

        # Exchange authorization code for tokens
        # oauthlib may raise Warning exception if returned scopes differ from requested
        logger.debug("[OAuth] Fetching token from Google...")
        try:
            flow.fetch_token(code=code)
        except Warning as w:
            # This is expected when Google grants fewer scopes than requested
            # The credentials are still populated, so we can continue
            logger.warning(f"[OAuth] Scope mismatch during token exchange (this is expected): {w}")

        credentials = flow.credentials
        logger.debug(f"[OAuth] Token fetch complete — credentials={'present' if credentials else 'MISSING'}")

        # Verify we got credentials despite potential scope mismatch
        if not credentials:
            raise ValueError("Failed to obtain credentials from OAuth flow")

        if not credentials.refresh_token:
            # This is expected when prompt=select_account is used and the user already
            # granted consent previously. Google re-issues an access token but omits
            # the refresh token. The caller must merge the existing DB refresh token.
            logger.info("[OAuth] No refresh_token in response — will reuse existing DB token (expected for prompt=select_account)")
        else:
            logger.debug("[OAuth] Got refresh_token in response")

        logger.debug(
            f"[OAuth] Got tokens — access_token={'present' if credentials.token else 'MISSING'}, "
            f"refresh_token={'present' if credentials.refresh_token else 'absent'}, expiry={credentials.expiry}"
        )

        # Extract email from ID token
        # The ID token might be a JWT string that needs to be decoded
        raw_id_token = credentials.id_token
        if not raw_id_token:
            logger.error("[OAuth] Credentials object has no id_token")
            raise ValueError("Could not get ID token from credentials")

        logger.debug(f"[OAuth] Decoding ID token (type={type(raw_id_token).__name__})")

        # Decode the ID token if it's a string (JWT)
        if isinstance(raw_id_token, str):
            try:
                client_id, _, _ = get_oauth_config()
                id_token_claims = google_id_token.verify_oauth2_token(
                    raw_id_token,
                    google_requests.Request(),
                    client_id
                )
                logger.debug(f"[OAuth] ID token verified — claims: {list(id_token_claims.keys())}")
            except Exception as e:
                logger.error(f"[OAuth] Failed to verify ID token: {e}")
                raise ValueError(f"Failed to decode ID token: {e}")
        else:
            # Already a dict
            id_token_claims = raw_id_token
            logger.debug(f"[OAuth] ID token already decoded — claims: {list(id_token_claims.keys())}")

        if "email" not in id_token_claims:
            logger.error(f"[OAuth] ID token missing email claim. Claims: {list(id_token_claims.keys())}")
            raise ValueError("ID token does not contain email claim")

        email = id_token_claims["email"]
        logger.info(f"[OAuth] Extracted email from ID token: {email}")

        # Check if email is allowed (if restriction is set)
        allowed_email = get_allowed_email()
        if allowed_email:
            logger.debug(f"[OAuth] Checking email restriction — allowed: {allowed_email}")
            if email.lower() != allowed_email.lower():
                logger.warning(f"[OAuth] Rejected OAuth for email {email} (allowed: {allowed_email})")
                raise ValueError(f"Email {email} is not authorized. Only {allowed_email} is allowed.")
            logger.debug(f"[OAuth] Email {email} matches allowed email")

        # Log what scopes were actually granted
        granted_scopes = credentials.scopes or []
        logger.info(f"[OAuth] Token exchange successful for {email} — granted scopes: {granted_scopes}")
        return credentials

    except RefreshError as e:
        logger.error(f"[OAuth] Token exchange failed (RefreshError): {e}")
        raise ValueError(f"Failed to exchange code for tokens: {e}") from e
    except ValueError:
        # Re-raise ValueError as-is (from our own validation above)
        raise
    except Exception as e:
        logger.error(f"[OAuth] Unexpected error during token exchange: {e}")
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
    logger.info(f"[OAuth] Starting access token refresh (refresh_token={refresh_token_str[:8]}...)")
    try:
        client_id, client_secret, _ = get_oauth_config()

        # Create a Credentials object from the refresh token
        logger.debug("[OAuth] Creating Credentials object for refresh")
        credentials = Credentials(
            token=None,  # No access token yet
            refresh_token=refresh_token_str,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=GMAIL_SCOPES,
        )

        # Refresh the credentials
        logger.debug("[OAuth] Sending refresh request to Google...")
        request = Request()
        credentials.refresh(request)

        if not credentials.token:
            logger.error("[OAuth] Token refresh response missing access_token")
            raise ValueError("Token refresh response missing access_token")

        # Get expiry datetime (SDK provides this directly)
        expiry_dt = credentials.expiry or datetime.now(timezone.utc)

        logger.info(f"[OAuth] Successfully refreshed access token (new expiry: {expiry_dt.isoformat()})")
        return credentials.token, expiry_dt

    except RefreshError as e:
        logger.error(f"[OAuth] Token refresh failed (RefreshError): {e}")
        raise ValueError(f"Failed to refresh token: {e}") from e
    except Exception as e:
        logger.error(f"[OAuth] Unexpected error during token refresh: {e}")
        raise


def get_email_from_credentials(credentials: Credentials) -> Optional[str]:
    """Extract email from Credentials ID token.

    Args:
        credentials: Google OAuth2 Credentials object

    Returns:
        User's email address if available in ID token, None otherwise
    """
    logger.debug("[OAuth] Extracting email from credentials ID token")
    if not credentials.id_token:
        logger.debug("[OAuth] No ID token present in credentials")
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
            email = id_token_claims.get("email")
            logger.debug(f"[OAuth] Extracted email from JWT ID token: {email}")
            return email
        except Exception as e:
            logger.debug(f"[OAuth] Failed to decode ID token: {e}")
            return None
    else:
        # Already a dict
        email = credentials.id_token.get("email")
        logger.debug(f"[OAuth] Extracted email from dict ID token: {email}")
        return email

