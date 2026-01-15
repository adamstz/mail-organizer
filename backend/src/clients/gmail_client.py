"""Gmail API helper utilities.

These helpers wrap the Google client library to keep Gmail-specific logic in one
place. They intentionally focus on read/modify access that the backend needs
once a Pub/Sub notification arrives.
"""
from __future__ import annotations

import os
import logging
from typing import Iterable, List, Optional, Sequence, Set
from datetime import datetime, timezone

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import Resource, build

logger = logging.getLogger(__name__)

DEFAULT_GMAIL_SCOPES: Sequence[str] = (
    # Read-only access will not let us modify labels or ack history. We default
    # to readonly so downstream code won't attempt to modify messages unless
    # explicitly changed. Use gmail.modify only when you need to change labels
    # or state.
    "https://www.googleapis.com/auth/gmail.readonly",
)


def build_credentials_from_oauth(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: Iterable[str] = DEFAULT_GMAIL_SCOPES,
) -> OAuthCredentials:
    """Build OAuth2 credentials from client ID, secret, and refresh token.

    Use this when you have OAuth credentials (e.g., from Codespace secrets)
    instead of service account credentials.
    """
    return OAuthCredentials(
        token=None,  # Will be refreshed automatically
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
    )


def build_credentials_from_db(email: Optional[str] = None) -> Optional[OAuthCredentials]:
    """Build OAuth2 credentials from tokens stored in the database.
    
    This is the preferred method for self-hosted deployments using the OAuth flow.
    Falls back to environment variables if no tokens are found in the database.
    
    Args:
        email: Specific email to get tokens for. If None, gets the first authenticated user.
    
    Returns:
        OAuthCredentials if tokens found, None otherwise
    """
    # Import here to avoid circular imports
    from .. import storage
    
    # Get OAuth config from environment (needed for client_id/secret)
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.warning("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set")
        return None
    
    # Try to get tokens from database
    try:
        if email:
            tokens = storage.get_oauth_tokens(email)
        else:
            # Get the first/only authenticated user for single-user deployments
            authenticated_email = storage.get_authenticated_email()
            if not authenticated_email:
                logger.debug("No authenticated user found in database")
                return None
            tokens = storage.get_oauth_tokens(authenticated_email)
        
        if not tokens:
            logger.debug(f"No OAuth tokens found for email: {email or 'any'}")
            return None
        
        logger.debug(f"Building credentials from database for: {tokens['email']}")
        
        return OAuthCredentials(
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=list(DEFAULT_GMAIL_SCOPES),
        )
        
    except Exception as e:
        logger.error(f"Error getting tokens from database: {e}")
        return None


def get_gmail_credentials(email: Optional[str] = None) -> Optional[Credentials]:
    """Get Gmail credentials using the best available method.
    
    Priority:
    1. Database-stored OAuth tokens (from OAuth flow)
    2. Environment variable credentials (GOOGLE_REFRESH legacy method)
    3. Application Default Credentials (for service accounts)
    
    Args:
        email: Specific email to get tokens for (optional)
    
    Returns:
        Credentials object if available, None otherwise
    """
    # Try database first (OAuth flow)
    creds = build_credentials_from_db(email)
    if creds:
        logger.debug("Using credentials from database")
        return creds
    
    # Fall back to environment variables (legacy method)
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH")
    
    if client_id and client_secret and refresh_token:
        logger.debug("Using credentials from environment variables (legacy)")
        return build_credentials_from_oauth(client_id, client_secret, refresh_token)
    
    # Fall back to Application Default Credentials
    try:
        logger.debug("Attempting Application Default Credentials")
        creds, _ = google.auth.default(scopes=list(DEFAULT_GMAIL_SCOPES))
        return creds
    except Exception as e:
        logger.debug(f"ADC not available: {e}")
    
    return None


def build_gmail_service(
    credentials: Credentials | None = None,
    scopes: Iterable[str] = DEFAULT_GMAIL_SCOPES,
    *,
    cache_discovery: bool = False,
    user_agent: str | None = None,
    email: str | None = None,
) -> Resource:
    """Return an authenticated Gmail API client (`googleapiclient.discovery.Resource`).

    If `credentials` is omitted, the function tries multiple credential sources:
    1. Database-stored OAuth tokens (from OAuth flow)
    2. Environment variable credentials (GOOGLE_REFRESH legacy method)
    3. Application Default Credentials

    The helper also refreshes expiring credentials and updates the database
    with new access tokens if using database-stored credentials.
    
    Args:
        credentials: Optional pre-built credentials
        scopes: OAuth scopes to request
        cache_discovery: Whether to cache API discovery document
        user_agent: Optional user agent string
        email: Email address to get credentials for (when using database tokens)
    """
    scopes_list = list(scopes)

    if credentials is None:
        credentials = get_gmail_credentials(email)
        
        if credentials is None:
            raise ValueError(
                "No Gmail credentials available. Either:\n"
                "1. Complete the OAuth flow at /api/auth/login\n"
                "2. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH env vars\n"
                "3. Configure Application Default Credentials"
            )

    requires_scopes = getattr(credentials, "requires_scopes", False)
    if requires_scopes and scopes_list:
        credentials = credentials.with_scopes(scopes_list)

    if not credentials.valid:
        request = Request()
        credentials.refresh(request)
        
        # If using OAuth credentials, update the access token in database
        if isinstance(credentials, OAuthCredentials) and credentials.token:
            try:
                from .. import storage
                # Get the email associated with these credentials
                # For OAuthCredentials built from DB, we can track which user
                authenticated_email = storage.get_authenticated_email()
                if authenticated_email:
                    # Calculate new expiry (Google access tokens typically last 1 hour)
                    new_expiry = datetime.now(timezone.utc).replace(
                        hour=datetime.now(timezone.utc).hour + 1
                    )
                    storage.update_access_token(
                        authenticated_email,
                        credentials.token,
                        new_expiry
                    )
                    logger.debug(f"Updated access token in database for {authenticated_email}")
            except Exception as e:
                logger.warning(f"Failed to update access token in database: {e}")

    discovery_kwargs = {"cache_discovery": cache_discovery}
    if user_agent:
        discovery_kwargs["client_options"] = {"user_agent": user_agent}

    return build("gmail", "v1", credentials=credentials, **discovery_kwargs)


def fetch_messages_by_history(
    gmail_service: Resource,
    start_history_id: str,
    *,
    user_id: str = "me",
    history_types: Sequence[str] | None = ("messageAdded",),
) -> List[str]:
    """Return message IDs added since `start_history_id`.

    Gmail's history API returns records per history event. We only collect the
    IDs for messages that were newly added (defaults to `messageAdded`) and we
    de-duplicate because the API can surface the same message multiple times
    across pages.
    """
    history_resource = gmail_service.users().history()  # type: ignore[attr-defined]
    request = history_resource.list(
        userId=user_id,
        startHistoryId=start_history_id,
        historyTypes=list(history_types) if history_types else None,
    )

    message_ids: List[str] = []
    seen: Set[str] = set()

    while request is not None:
        response = request.execute()
        for record in response.get("history", []):
            for added in record.get("messagesAdded", []):
                message = added.get("message") or {}
                message_id = message.get("id")
                if message_id and message_id not in seen:
                    seen.add(message_id)
                    message_ids.append(message_id)

        request = history_resource.list_next(request, response)

    return message_ids


def fetch_message(
    gmail_service: Resource,
    message_id: str,
    *,
    user_id: str = "me",
    format: str = "full",
) -> dict:
    """Fetch and return a single Gmail message payload.

    The `format` argument accepts the same values as the Gmail API (`minimal`,
    `metadata`, `full`, `raw`). Downstream code can parse headers/body from the
    returned dict.
    """
    messages_resource = gmail_service.users().messages()  # type: ignore[attr-defined]
    return messages_resource.get(userId=user_id, id=message_id, format=format).execute()


def extract_message_snippet(message: dict) -> str:
    """Return the small text snippet Gmail includes in each message summary."""
    return message.get("snippet", "")


def register_watch(
    gmail_service: Resource,
    topic_name: str,
    *,
    user_id: str = "me",
    label_ids: list | None = None,
) -> dict:
    """Register a Gmail watch to publish notifications to a Pub/Sub topic.

    topic_name should be the full resource name, e.g.:
      projects/PROJECT_ID/topics/TOPIC_NAME

    Returns the API response (contains expiration and historyId).
    """
    body = {"topicName": topic_name}
    if label_ids:
        body["labelIds"] = label_ids
    return gmail_service.users().watch(userId=user_id, body=body).execute()

