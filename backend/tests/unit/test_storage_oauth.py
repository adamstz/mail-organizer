"""Unit tests for OAuth token storage methods.

Tests the is_gmail_connected method for checking token validity.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.storage.memory_storage import InMemoryStorage


class TestIsGmailConnected:
    """Tests for the is_gmail_connected storage method."""

    @pytest.fixture
    def storage(self):
        """Create a fresh in-memory storage instance."""
        mem = InMemoryStorage()
        mem.init_db()
        return mem

    def test_no_tokens_returns_not_connected(self, storage):
        """When no tokens exist, should return not connected."""
        result = storage.is_gmail_connected("nonexistent@gmail.com")

        assert result["connected"] is False
        assert result["can_refresh"] is False
        assert result["token_expiry"] is None

    def test_valid_tokens_returns_connected(self, storage):
        """When tokens exist and are not expired, should return connected."""
        email = "user@gmail.com"
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        storage.save_oauth_tokens(
            email=email,
            access_token="valid_access_token",
            refresh_token="valid_refresh_token",
            token_expiry=future_expiry,
        )

        result = storage.is_gmail_connected(email)

        assert result["connected"] is True
        assert result["can_refresh"] is True
        assert result["token_expiry"] == future_expiry

    def test_expired_tokens_with_refresh_returns_can_refresh(self, storage):
        """When tokens are expired but refresh token exists, should indicate can_refresh."""
        email = "user@gmail.com"
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)

        storage.save_oauth_tokens(
            email=email,
            access_token="expired_access_token",
            refresh_token="valid_refresh_token",
            token_expiry=past_expiry,
        )

        result = storage.is_gmail_connected(email)

        assert result["connected"] is False
        assert result["can_refresh"] is True
        assert result["token_expiry"] == past_expiry

    def test_expired_tokens_without_refresh_returns_not_connected(self, storage):
        """When tokens are expired and no refresh token, should return not connected."""
        email = "user@gmail.com"
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)

        storage.save_oauth_tokens(
            email=email,
            access_token="expired_access_token",
            refresh_token=None,
            token_expiry=past_expiry,
        )

        result = storage.is_gmail_connected(email)

        assert result["connected"] is False
        assert result["can_refresh"] is False
        assert result["token_expiry"] == past_expiry

    def test_valid_tokens_without_refresh_still_connected(self, storage):
        """When tokens are valid but no refresh token, should still be connected."""
        email = "user@gmail.com"
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        storage.save_oauth_tokens(
            email=email,
            access_token="valid_access_token",
            refresh_token=None,
            token_expiry=future_expiry,
        )

        result = storage.is_gmail_connected(email)

        assert result["connected"] is True
        assert result["can_refresh"] is False
        assert result["token_expiry"] == future_expiry
