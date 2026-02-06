"""In-memory LRU cache for query results.

This module provides session-based caching of query result message IDs,
enabling follow-up queries like "list those 78 emails" to retrieve
the exact same results as the original count/search query.
"""
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CachedResult:
    """A cached query result with message IDs and metadata."""
    message_ids: List[str]
    query: str
    query_type: str
    timestamp: float = field(default_factory=time.time)
    total_count: Optional[int] = None  # Original count if truncated

    @property
    def is_truncated(self) -> bool:
        """Check if results were truncated to fit cache limit."""
        return self.total_count is not None and self.total_count > len(self.message_ids)


class ResultCache:
    """LRU cache for query results, keyed by session ID.

    Thread-safe implementation with configurable:
    - max_sessions: Maximum number of sessions to cache (LRU eviction)
    - ttl_seconds: Time-to-live for cached results
    - max_ids_per_result: Maximum message IDs to store per query result
    """

    def __init__(
        self,
        max_sessions: int = 100,
        ttl_seconds: int = 1800,  # 30 minutes
        max_ids_per_result: int = 500,
    ):
        """Initialize the cache.

        Args:
            max_sessions: Maximum number of sessions to cache
            ttl_seconds: TTL for cached results (default 30 minutes)
            max_ids_per_result: Maximum IDs to store per result (default 500)
        """
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self.max_ids_per_result = max_ids_per_result
        self._cache: OrderedDict[str, CachedResult] = OrderedDict()
        self._lock = Lock()

        logger.info(
            "[RESULT_CACHE] Initialized with max_sessions=%d, ttl=%ds, max_ids=%d",
            max_sessions, ttl_seconds, max_ids_per_result
        )

    def store(
        self,
        session_id: str,
        message_ids: List[str],
        query: str,
        query_type: str,
        total_count: Optional[int] = None,
    ) -> None:
        """Store query result message IDs for a session.

        Args:
            session_id: The chat session ID
            message_ids: List of message IDs from the query result
            query: The original query string
            query_type: Type of query that produced these results
            total_count: Original total count if results were truncated
        """
        if not session_id or not message_ids:
            return

        # Cap the number of IDs stored
        stored_ids = message_ids[:self.max_ids_per_result]
        actual_total = total_count if total_count is not None else len(message_ids)

        with self._lock:
            # Remove if exists (to update LRU order)
            if session_id in self._cache:
                del self._cache[session_id]

            # Add new entry
            self._cache[session_id] = CachedResult(
                message_ids=stored_ids,
                query=query,
                query_type=query_type,
                total_count=actual_total if actual_total > len(stored_ids) else None,
            )

            # Evict oldest entries if over capacity
            while len(self._cache) > self.max_sessions:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("[RESULT_CACHE] Evicted session %s (LRU)", evicted_key)

            logger.debug(
                "[RESULT_CACHE] Stored %d IDs for session %s (total: %s, truncated: %s)",
                len(stored_ids), session_id, actual_total,
                actual_total > len(stored_ids) if actual_total else False
            )

    def get(self, session_id: str) -> Optional[CachedResult]:
        """Retrieve cached result for a session.

        Args:
            session_id: The chat session ID

        Returns:
            CachedResult if found and not expired, None otherwise
        """
        if not session_id:
            return None

        with self._lock:
            result = self._cache.get(session_id)
            if result is None:
                logger.debug("[RESULT_CACHE] Cache miss for session %s", session_id)
                return None

            # Check TTL
            age = time.time() - result.timestamp
            if age > self.ttl_seconds:
                del self._cache[session_id]
                logger.debug(
                    "[RESULT_CACHE] Expired entry for session %s (age: %.1fs)",
                    session_id, age
                )
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(session_id)
            logger.debug(
                "[RESULT_CACHE] Cache hit for session %s (%d IDs, age: %.1fs)",
                session_id, len(result.message_ids), age
            )
            return result

    def clear(self, session_id: Optional[str] = None) -> None:
        """Clear cache entries.

        Args:
            session_id: If provided, clear only that session. Otherwise clear all.
        """
        with self._lock:
            if session_id:
                if session_id in self._cache:
                    del self._cache[session_id]
                    logger.debug("[RESULT_CACHE] Cleared session %s", session_id)
            else:
                self._cache.clear()
                logger.info("[RESULT_CACHE] Cleared all cached results")

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        now = time.time()
        removed = 0

        with self._lock:
            expired_keys = [
                key for key, result in self._cache.items()
                if now - result.timestamp > self.ttl_seconds
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1

        if removed:
            logger.info("[RESULT_CACHE] Cleaned up %d expired entries", removed)
        return removed

    @property
    def size(self) -> int:
        """Current number of cached sessions."""
        return len(self._cache)


# Global singleton instance
_result_cache: Optional[ResultCache] = None


def get_result_cache() -> ResultCache:
    """Get the global result cache singleton.

    Returns:
        The global ResultCache instance
    """
    global _result_cache
    if _result_cache is None:
        _result_cache = ResultCache()
    return _result_cache
