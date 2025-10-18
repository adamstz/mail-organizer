"""Local LLM processor stubs.

This module will contain wrappers to call a local LLM for categorization and
content processing. Keep it decoupled from actual model implementations.
"""
from typing import Any, Dict


class LLMProcessor:
    def __init__(self, config: Dict | None = None):
        self.config = config or {}

    def categorize_message(self, subject: str, body: str) -> Dict:
        """Return a classification dict for a message.

        Example return: {"labels": ["finance", "important"], "priority": "high"}
        """
        # Placeholder: replace with LLM call
        return {"labels": [], "priority": "normal"}

