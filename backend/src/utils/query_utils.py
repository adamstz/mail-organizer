"""Query parsing utilities for extracting information from user queries."""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_number_from_query(
    question: str,
    default: Optional[int] = 10,
    max_limit: int = 100
) -> Optional[int]:
    """Extract a number from the query to use as the result limit.

    Patterns matched:
    - "last 10 emails", "recent 5 messages"
    - "show me 20 emails", "get 15 messages"
    - "10 emails from...", "25 messages about..."
    - "top 5 results"

    Args:
        question: User's question
        default: Default limit if no number found (None means return None when no match)
        max_limit: Maximum allowed limit (cap for safety)

    Returns:
        Extracted number clamped to [1, max_limit], or default if none found
        Returns None when default is None and no number is found in the query
    """
    patterns = [
        r'\b(?:last|recent|latest|past)\s+(\d+)\b',
        r'\b(?:show|get|find|list|give)\s+(?:me\s+)?(?:the\s+)?(\d+)\b',
        r'\b(\d+)\s+(?:emails?|messages?|mails?|results?)\b',
        r'\btop\s+(\d+)\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            num = int(match.group(1))
            if 1 <= num <= max_limit:
                return num
            elif num > max_limit:
                return max_limit

    return default
