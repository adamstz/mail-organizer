"""Authentication module for OAuth and JWT handling."""

from .oauth import (
    get_google_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_email_from_credentials,
    generate_oauth_state,
    verify_oauth_state,
)
from .middleware import (
    get_current_user,
    require_auth,
    create_jwt_token,
    JWT_COOKIE_NAME,
    OAUTH_STATE_COOKIE_NAME,
    AuthenticatedUser,
    set_oauth_state_cookie,
    clear_oauth_state_cookie,
)

__all__ = [
    "get_google_auth_url",
    "exchange_code_for_tokens",
    "refresh_access_token",
    "get_email_from_credentials",
    "get_current_user",
    "require_auth",
    "create_jwt_token",
    "JWT_COOKIE_NAME",
    "OAUTH_STATE_COOKIE_NAME",
    "AuthenticatedUser",
    "generate_oauth_state",
    "verify_oauth_state",
    "set_oauth_state_cookie",
    "clear_oauth_state_cookie",
]
