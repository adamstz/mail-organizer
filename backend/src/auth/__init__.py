"""Authentication module for OAuth and JWT handling."""

from .oauth import (
    get_google_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_user_email_from_token,
)
from .middleware import (
    get_current_user,
    require_auth,
    create_jwt_token,
    JWT_COOKIE_NAME,
    AuthenticatedUser,
)

__all__ = [
    "get_google_auth_url",
    "exchange_code_for_tokens",
    "refresh_access_token",
    "get_user_email_from_token",
    "get_current_user",
    "require_auth",
    "create_jwt_token",
    "JWT_COOKIE_NAME",
    "AuthenticatedUser",
]
