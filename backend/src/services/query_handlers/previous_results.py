"""Handler for follow-up queries requesting previous results.

This handler retrieves emails from a cached result set when users ask
follow-up questions like "list those 78 emails" or "show them to me".
"""
from typing import Dict, Optional
import logging

from .base import QueryHandler
from ..result_cache import get_result_cache, CachedResult

logger = logging.getLogger(__name__)


class PreviousResultsHandler(QueryHandler):
    """Handle queries that request listing of previous search results.

    Uses the result cache to retrieve message IDs from a prior query
    and fetches the full message details.
    """

    def handle(
        self,
        question: str,
        limit: int = 20,
        chat_history: Optional[list] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """Handle a request to list previous query results.

        Args:
            question: User's question (e.g., "list those 78 emails")
            limit: Maximum number of emails to return
            chat_history: Previous conversation messages
            session_id: Chat session ID for cache lookup

        Returns:
            Query result with answer and sources
        """
        logger.info(
            "[PREVIOUS_RESULTS] Processing list-previous-results query, session: %s",
            session_id
        )

        # Try to get cached results
        cache = get_result_cache()
        cached: Optional[CachedResult] = None

        if session_id:
            cached = cache.get(session_id)

        if not cached:
            logger.warning("[PREVIOUS_RESULTS] No cached results found for session")
            return self._build_response(
                answer=(
                    "I don't have any previous search results to show. "
                    "Could you please specify what you'd like me to search for?"
                ),
                sources=[],
                question=question,
                query_type='list-previous-results',
                confidence='none',
            )

        logger.info(
            "[PREVIOUS_RESULTS] Found cached results: %d IDs from query '%s' (type: %s)",
            len(cached.message_ids),
            cached.query[:50],
            cached.query_type
        )

        # Retrieve messages by IDs
        message_ids_to_fetch = cached.message_ids[:limit]
        messages = self.storage.get_messages_by_ids(message_ids_to_fetch)

        if not messages:
            logger.warning("[PREVIOUS_RESULTS] No messages found for cached IDs")
            return self._build_response(
                answer="I couldn't retrieve the emails from the previous search. They may have been deleted or moved.",
                sources=[],
                question=question,
                query_type='list-previous-results',
                confidence='low',
            )

        # Format sources
        sources = self._format_sources(messages)

        # Build answer
        total_available = len(cached.message_ids)
        original_total = cached.total_count if cached.is_truncated else total_available
        showing = len(messages)

        if cached.is_truncated:
            answer = (
                f"Here are {showing} of the {original_total:,} emails from your previous search "
                f"for '{cached.query}'."
            )
            if showing < original_total:
                answer += f" (I can show up to {total_available} at a time.)"
        else:
            answer = (
                f"Here are the {showing} emails from your previous search for '{cached.query}'."
            )

        # Include cached IDs in response for potential further follow-ups
        return self._build_response(
            answer=answer,
            sources=sources,
            question=question,
            query_type='list-previous-results',
            confidence='high',
            total_count=original_total,
            cached_message_ids=cached.message_ids,
        )
