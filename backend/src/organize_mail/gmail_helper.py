"""Gmail API helper utilities (stubs).

These functions are intentionally minimal — fill in with auth and retry logic later.
"""
from typing import Any, List


def fetch_messages_by_history(gmail_service: Any, start_history_id: str) -> List[str]:
    """Return a list of message IDs added since start_history_id.

    This is a small wrapper around `users.history.list`.
    """
    # Implementation placeholder
    return []


def fetch_message(gmail_service: Any, message_id: str) -> dict:
    """Fetch a single message by id and return the API payload.
    """
    return {}
