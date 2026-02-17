"""Unit tests for dynamic query limit extraction."""
import os
import pytest

# Set test environment before imports
os.environ["LLM_PROVIDER"] = "rules"

from src.utils.query_utils import extract_number_from_query
from src.services.query_classifier import QueryClassifier
from src.services.llm_processor import LLMProcessor
from unittest.mock import patch


class TestExtractNumberFromQuery:
    """Test extract_number_from_query function."""

    def test_last_n_emails(self):
        """Extract number from 'last N emails' pattern."""
        assert extract_number_from_query("my last 10 emails") == 10
        assert extract_number_from_query("show me the last 5 messages") == 5
        assert extract_number_from_query("last 20 job application emails") == 20

    def test_recent_n_pattern(self):
        """Extract number from 'recent N' pattern."""
        assert extract_number_from_query("my recent 15 emails") == 15
        assert extract_number_from_query("latest 8 messages from Amazon") == 8

    def test_show_get_find_pattern(self):
        """Extract number from 'show/get/find N' pattern."""
        assert extract_number_from_query("show me 10 emails about invoices") == 10
        assert extract_number_from_query("get 7 messages from HR") == 7
        assert extract_number_from_query("find 12 emails with attachments") == 12
        assert extract_number_from_query("list 25 messages") == 25

    def test_n_emails_pattern(self):
        """Extract number from 'N emails/messages' pattern."""
        assert extract_number_from_query("10 emails from Amazon") == 10
        assert extract_number_from_query("15 messages about shipping") == 15
        assert extract_number_from_query("give me 8 results") == 8

    def test_top_n_pattern(self):
        """Extract number from 'top N' pattern."""
        assert extract_number_from_query("top 5 recent emails") == 5
        assert extract_number_from_query("show top 10 senders") == 10

    def test_no_number_returns_default(self):
        """Return default when no number in query."""
        assert extract_number_from_query("show me my emails") == 10
        assert extract_number_from_query("what job applications do I have?") == 10
        assert extract_number_from_query("emails from Amazon") == 10

    def test_custom_default(self):
        """Respect custom default value."""
        assert extract_number_from_query("show my emails", default=20) == 20
        assert extract_number_from_query("job applications", default=5) == 5

    def test_cap_at_max_limit(self):
        """Numbers above max_limit should be capped."""
        assert extract_number_from_query("show me 500 emails") == 100
        assert extract_number_from_query("last 200 messages") == 100
        assert extract_number_from_query("last 150 emails", max_limit=50) == 50

    def test_ignore_invalid_numbers(self):
        """Numbers below 1 should be ignored."""
        # Zero should return default
        assert extract_number_from_query("0 emails") == 10

    def test_case_insensitive(self):
        """Pattern matching should be case-insensitive."""
        assert extract_number_from_query("LAST 10 EMAILS") == 10
        assert extract_number_from_query("Show Me 15 Messages") == 15
        assert extract_number_from_query("RECENT 8 mails") == 8

    def test_first_match_wins(self):
        """When multiple numbers present, first matching pattern wins."""
        # "last 10" matches first
        assert extract_number_from_query("last 10 emails, not 5") == 10

    def test_real_world_queries(self):
        """Test realistic user queries."""
        assert extract_number_from_query("my last 10 job application emails? what company") == 10
        assert extract_number_from_query("show me the last 25 emails from recruiters") == 25
        assert extract_number_from_query("what are my recent 5 shipping notifications?") == 5
        assert extract_number_from_query("list 30 unread messages") == 30
        assert extract_number_from_query("find me 50 emails about invoices from last month") == 50

    def test_default_none_mode(self):
        """When default=None, return None if no number found."""
        assert extract_number_from_query("show me my emails", default=None) is None
        assert extract_number_from_query("emails from Amazon", default=None) is None
        assert extract_number_from_query("what job applications?", default=None) is None
        # But still extract if present
        assert extract_number_from_query("last 10 emails", default=None) == 10


@pytest.fixture
def query_classifier():
    """Create a QueryClassifier instance for testing."""
    with patch.object(LLMProcessor, '_is_ollama_running', return_value=False):
        llm = LLMProcessor()
    return QueryClassifier(llm)


class TestLLMCountExtraction:
    """Test LLM-based count extraction via QueryClassifier."""
    
    def test_parse_classification_with_count(self, query_classifier):
        """Test parsing 'type,count' format from LLM."""
        query_type, count = query_classifier._parse_classification("temporal,10")
        assert query_type == "temporal"
        assert count == 10

    def test_parse_classification_with_none_count(self, query_classifier):
        """Test parsing 'type,none' format."""
        query_type, count = query_classifier._parse_classification("semantic,none")
        assert query_type == "semantic"
        assert count is None

    def test_parse_classification_no_count(self, query_classifier):
        """Test backward compatibility - just type without comma."""
        query_type, count = query_classifier._parse_classification("conversation")
        assert query_type == "conversation"
        assert count is None

    def test_parse_classification_with_whitespace(self, query_classifier):
        """Test parsing with whitespace around comma."""
        query_type, count = query_classifier._parse_classification("search-by-sender, 25")
        assert query_type == "search-by-sender"
        assert count == 25

    def test_parse_classification_caps_count(self, query_classifier):
        """Test that count is capped at max_limit (100)."""
        query_type, count = query_classifier._parse_classification("temporal,500")
        assert query_type == "temporal"
        assert count == 100

    def test_parse_classification_floors_count(self, query_classifier):
        """Test that count below 1 is ignored."""
        query_type, count = query_classifier._parse_classification("temporal,0")
        assert query_type == "temporal"
        assert count is None
        
        query_type, count = query_classifier._parse_classification("temporal,-5")
        assert query_type == "temporal"
        assert count is None

    def test_parse_classification_invalid_count(self, query_classifier):
        """Test that non-numeric count is ignored."""
        query_type, count = query_classifier._parse_classification("temporal,invalid")
        assert query_type == "temporal"
        assert count is None

    def test_fallback_classification_extracts_count(self, query_classifier):
        """Test that fallback classification uses regex to extract count."""
        query_type, count = query_classifier._fallback_classification("last 10 emails")
        assert query_type == "temporal"
        assert count == 10

    def test_fallback_classification_no_count(self, query_classifier):
        """Test fallback when no count in query."""
        query_type, count = query_classifier._fallback_classification("hello")
        assert query_type == "conversation"
        assert count is None

    def test_detect_query_type_returns_tuple(self, query_classifier):
        """Test that detect_query_type returns (type, count) tuple."""
        query_type, count = query_classifier.detect_query_type("last 10 emails")
        assert isinstance(query_type, str)
        assert query_type in query_classifier.VALID_TYPES
        # Count might be extracted by fallback (rules provider uses fallback)
        assert count is None or isinstance(count, int)


