"""Tests for result cache functionality."""
import time
import pytest

from src.services.result_cache import ResultCache, get_result_cache, CachedResult


class TestResultCache:
    """Tests for ResultCache class."""

    def test_store_and_get(self):
        """Should store and retrieve cached results."""
        cache = ResultCache(max_sessions=10, ttl_seconds=60)
        
        cache.store(
            session_id="session1",
            message_ids=["msg1", "msg2", "msg3"],
            query="test query",
            query_type="aggregation",
        )
        
        result = cache.get("session1")
        assert result is not None
        assert result.message_ids == ["msg1", "msg2", "msg3"]
        assert result.query == "test query"
        assert result.query_type == "aggregation"

    def test_max_ids_per_result(self):
        """Should cap message IDs at max_ids_per_result."""
        cache = ResultCache(max_ids_per_result=5)
        
        cache.store(
            session_id="session1",
            message_ids=[f"msg{i}" for i in range(100)],
            query="test query",
            query_type="aggregation",
            total_count=100,
        )
        
        result = cache.get("session1")
        assert result is not None
        assert len(result.message_ids) == 5
        assert result.total_count == 100
        assert result.is_truncated is True

    def test_lru_eviction(self):
        """Should evict oldest entries when max_sessions exceeded."""
        cache = ResultCache(max_sessions=2)
        
        cache.store("session1", ["msg1"], "query1", "semantic")
        cache.store("session2", ["msg2"], "query2", "semantic")
        cache.store("session3", ["msg3"], "query3", "semantic")  # Should evict session1
        
        assert cache.get("session1") is None
        assert cache.get("session2") is not None
        assert cache.get("session3") is not None

    def test_ttl_expiration(self):
        """Should expire entries after TTL."""
        cache = ResultCache(ttl_seconds=1)
        
        cache.store("session1", ["msg1"], "query1", "semantic")
        
        # Should be available immediately
        assert cache.get("session1") is not None
        
        # Wait for TTL to expire
        time.sleep(1.1)
        
        # Should be expired now
        assert cache.get("session1") is None

    def test_get_nonexistent(self):
        """Should return None for nonexistent sessions."""
        cache = ResultCache()
        assert cache.get("nonexistent") is None

    def test_get_empty_session_id(self):
        """Should return None for empty session ID."""
        cache = ResultCache()
        assert cache.get("") is None
        assert cache.get(None) is None

    def test_clear_specific_session(self):
        """Should clear only the specified session."""
        cache = ResultCache()
        
        cache.store("session1", ["msg1"], "query1", "semantic")
        cache.store("session2", ["msg2"], "query2", "semantic")
        
        cache.clear("session1")
        
        assert cache.get("session1") is None
        assert cache.get("session2") is not None

    def test_clear_all(self):
        """Should clear all sessions when no session_id provided."""
        cache = ResultCache()
        
        cache.store("session1", ["msg1"], "query1", "semantic")
        cache.store("session2", ["msg2"], "query2", "semantic")
        
        cache.clear()
        
        assert cache.get("session1") is None
        assert cache.get("session2") is None
        assert cache.size == 0


class TestCachedResult:
    """Tests for CachedResult dataclass."""

    def test_is_truncated_true(self):
        """Should return True when total_count > len(message_ids)."""
        result = CachedResult(
            message_ids=["msg1", "msg2"],
            query="test",
            query_type="aggregation",
            total_count=100,
        )
        assert result.is_truncated is True

    def test_is_truncated_false_when_no_total(self):
        """Should return False when total_count is None."""
        result = CachedResult(
            message_ids=["msg1", "msg2"],
            query="test",
            query_type="aggregation",
        )
        assert result.is_truncated is False

    def test_is_truncated_false_when_equal(self):
        """Should return False when total_count equals message count."""
        result = CachedResult(
            message_ids=["msg1", "msg2"],
            query="test",
            query_type="aggregation",
            total_count=2,
        )
        assert result.is_truncated is False


class TestGetResultCache:
    """Tests for get_result_cache singleton."""

    def test_returns_same_instance(self):
        """Should return the same cache instance."""
        cache1 = get_result_cache()
        cache2 = get_result_cache()
        assert cache1 is cache2
