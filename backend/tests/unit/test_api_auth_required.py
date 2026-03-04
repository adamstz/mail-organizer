"""
Unit tests for API endpoint authentication requirements.

Tests that protected endpoints return 401 when not authenticated
and work correctly when authenticated.
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set required environment variables before imports
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_unit_tests_only")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test_client_id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("LLM_PROVIDER", "rules")


class TestUnauthenticatedAccess:
    """Tests that endpoints return 401 when not authenticated."""

    @pytest.fixture
    def client(self):
        """Create an unauthenticated test client."""
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage

        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()

        with TestClient(app) as client:
            yield client

    # ==================== Message Endpoints ====================

    def test_get_messages_requires_auth(self, client):
        """Test GET /messages returns 401 without auth."""
        response = client.get("/messages")
        assert response.status_code == 401

    def test_get_message_by_id_requires_auth(self, client):
        """Test GET /messages/{id} returns 401 without auth."""
        response = client.get("/messages/test-id")
        assert response.status_code == 401

    def test_get_message_body_requires_auth(self, client):
        """Test GET /messages/{id}/body returns 401 without auth."""
        response = client.get("/messages/test-id/body")
        assert response.status_code == 401

    def test_get_message_classifications_requires_auth(self, client):
        """Test GET /messages/{id}/classifications returns 401 without auth."""
        response = client.get("/messages/test-id/classifications")
        assert response.status_code == 401

    def test_get_latest_classification_requires_auth(self, client):
        """Test GET /messages/{id}/classification/latest returns 401 without auth."""
        response = client.get("/messages/test-id/classification/latest")
        assert response.status_code == 401

    def test_reclassify_message_requires_auth(self, client):
        """Test POST /messages/{id}/reclassify returns 401 without auth."""
        response = client.post("/messages/test-id/reclassify", json={})
        assert response.status_code == 401

    # ==================== Delete Endpoints ====================

    def test_delete_message_requires_auth(self, client):
        """Test DELETE /api/messages/{id} returns 401 without auth."""
        response = client.delete("/api/messages/test-id")
        assert response.status_code == 401

    def test_batch_delete_messages_requires_auth(self, client):
        """Test DELETE /api/messages/batch returns 401 without auth."""
        response = client.request("DELETE", "/api/messages/batch", json={"ids": ["id1", "id2"]})
        assert response.status_code == 401

    # ==================== Filter Endpoints ====================

    def test_filter_by_priority_requires_auth(self, client):
        """Test GET /messages/filter/priority/{priority} returns 401 without auth."""
        response = client.get("/messages/filter/priority/high")
        assert response.status_code == 401

    def test_filter_by_label_requires_auth(self, client):
        """Test GET /messages/filter/label/{label} returns 401 without auth."""
        response = client.get("/messages/filter/label/work")
        assert response.status_code == 401

    def test_filter_classified_requires_auth(self, client):
        """Test GET /messages/filter/classified returns 401 without auth."""
        response = client.get("/messages/filter/classified")
        assert response.status_code == 401

    def test_filter_unclassified_requires_auth(self, client):
        """Test GET /messages/filter/unclassified returns 401 without auth."""
        response = client.get("/messages/filter/unclassified")
        assert response.status_code == 401

    def test_filter_advanced_requires_auth(self, client):
        """Test GET /messages/filter/advanced returns 401 without auth."""
        response = client.get("/messages/filter/advanced")
        assert response.status_code == 401

    # ==================== Stats Endpoints ====================

    def test_get_stats_requires_auth(self, client):
        """Test GET /stats returns 401 without auth."""
        response = client.get("/stats")
        assert response.status_code == 401

    def test_get_labels_requires_auth(self, client):
        """Test GET /labels returns 401 without auth."""
        response = client.get("/labels")
        assert response.status_code == 401

    # ==================== Model Endpoints ====================

    def test_list_models_requires_auth(self, client):
        """Test GET /models returns 401 without auth."""
        response = client.get("/models")
        assert response.status_code == 401

    def test_set_model_requires_auth(self, client):
        """Test POST /api/set-model returns 401 without auth."""
        response = client.post("/api/set-model", json={"model": "test-model"})
        assert response.status_code == 401

    def test_get_current_model_requires_auth(self, client):
        """Test GET /api/current-model returns 401 without auth."""
        response = client.get("/api/current-model")
        assert response.status_code == 401

    def test_start_ollama_requires_auth(self, client):
        """Test POST /api/ollama/start returns 401 without auth."""
        response = client.post("/api/ollama/start")
        assert response.status_code == 401

    # ==================== Sync Endpoints ====================

    def test_get_sync_status_requires_auth(self, client):
        """Test GET /api/sync-status returns 401 without auth."""
        response = client.get("/api/sync-status")
        assert response.status_code == 401

    def test_sync_pull_requires_auth(self, client):
        """Test POST /api/sync/pull returns 401 without auth."""
        response = client.post("/api/sync/pull")
        assert response.status_code == 401

    def test_sync_classify_requires_auth(self, client):
        """Test POST /api/sync/classify returns 401 without auth."""
        response = client.post("/api/sync/classify")
        assert response.status_code == 401

    # ==================== Query/RAG Endpoints ====================

    def test_query_emails_requires_auth(self, client):
        """Test POST /api/query returns 401 without auth."""
        response = client.post("/api/query", json={"question": "test question"})
        assert response.status_code == 401

    def test_embedding_status_requires_auth(self, client):
        """Test GET /api/embedding_status returns 401 without auth."""
        response = client.get("/api/embedding_status")
        assert response.status_code == 401

    # ==================== Chat Session Endpoints ====================

    def test_create_chat_session_requires_auth(self, client):
        """Test POST /api/chat-sessions returns 401 without auth."""
        response = client.post("/api/chat-sessions", json={})
        assert response.status_code == 401

    def test_list_chat_sessions_requires_auth(self, client):
        """Test GET /api/chat-sessions returns 401 without auth."""
        response = client.get("/api/chat-sessions")
        assert response.status_code == 401

    def test_get_chat_session_messages_requires_auth(self, client):
        """Test GET /api/chat-sessions/{id}/messages returns 401 without auth."""
        response = client.get("/api/chat-sessions/test-id/messages")
        assert response.status_code == 401

    def test_delete_chat_session_requires_auth(self, client):
        """Test DELETE /api/chat-sessions/{id} returns 401 without auth."""
        response = client.delete("/api/chat-sessions/test-id")
        assert response.status_code == 401

    def test_update_chat_session_requires_auth(self, client):
        """Test PATCH /api/chat-sessions/{id} returns 401 without auth."""
        response = client.patch("/api/chat-sessions/test-id", json={"title": "New Title"})
        assert response.status_code == 401

    # ==================== Log Endpoints ====================

    def test_get_logs_is_public(self, client):
        """Test GET /api/logs is accessible without auth (public debug endpoint)."""
        response = client.get("/api/logs")
        assert response.status_code == 200

    def test_frontend_log_is_public(self, client):
        """Test POST /api/frontend-log is accessible without auth (public debug endpoint)."""
        response = client.post("/api/frontend-log", json={
            "level": "info",
            "message": "test",
            "timestamp": "2024-01-01T00:00:00Z"
        })
        assert response.status_code == 200


class TestPublicEndpoints:
    """Tests that public endpoints remain accessible without auth."""

    @pytest.fixture
    def client(self):
        """Create an unauthenticated test client."""
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage

        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()

        with TestClient(app) as client:
            yield client

    def test_health_endpoint_public(self, client):
        """Test GET /health is accessible without auth."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_auth_callback_public(self, client):
        """Test GET /api/auth/callback is accessible (returns 422 for missing code, not 401)."""
        response = client.get("/api/auth/callback")
        # 422 = missing required 'code' param, not 401 unauthorized
        assert response.status_code == 422


class TestAuthenticatedAccess:
    """Tests that endpoints work correctly when authenticated."""

    @pytest.fixture
    def authenticated_client(self):
        """Create an authenticated test client."""
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage
        from src.auth.middleware import create_jwt_token, JWT_COOKIE_NAME

        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()

        # Create JWT token for test user
        token = create_jwt_token("testuser@gmail.com")

        with TestClient(app, cookies={JWT_COOKIE_NAME: token}) as client:
            yield client

    def test_get_messages_authenticated(self, authenticated_client):
        """Test GET /messages works when authenticated."""
        response = authenticated_client.get("/messages")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data

    def test_get_stats_authenticated(self, authenticated_client):
        """Test GET /stats works when authenticated."""
        response = authenticated_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data

    def test_get_labels_authenticated(self, authenticated_client):
        """Test GET /labels works when authenticated."""
        response = authenticated_client.get("/labels")
        assert response.status_code == 200
        data = response.json()
        assert "labels" in data

    def test_filter_classified_authenticated(self, authenticated_client):
        """Test GET /messages/filter/classified works when authenticated."""
        response = authenticated_client.get("/messages/filter/classified")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_filter_unclassified_authenticated(self, authenticated_client):
        """Test GET /messages/filter/unclassified works when authenticated."""
        response = authenticated_client.get("/messages/filter/unclassified")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_get_current_model_authenticated(self, authenticated_client):
        """Test GET /api/current-model works when authenticated."""
        response = authenticated_client.get("/api/current-model")
        assert response.status_code == 200
        data = response.json()
        assert "model" in data
        assert "provider" in data

    def test_get_logs_authenticated(self, authenticated_client):
        """Test GET /api/logs works when authenticated."""
        response = authenticated_client.get("/api/logs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.skip(reason="InMemoryStorage doesn't implement chat session methods")
    def test_list_chat_sessions_authenticated(self, authenticated_client):
        """Test GET /api/chat-sessions works when authenticated."""
        response = authenticated_client.get("/api/chat-sessions")
        assert response.status_code == 200
        data = response.json()
        assert "chat_sessions" in data

    @pytest.mark.skip(reason="InMemoryStorage doesn't implement chat session methods")
    def test_create_chat_session_authenticated(self, authenticated_client):
        """Test POST /api/chat-sessions works when authenticated."""
        response = authenticated_client.post("/api/chat-sessions", json={"title": "Test Chat"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "Test Chat"

    def test_delete_message_not_found_authenticated(self, authenticated_client):
        """Test DELETE /api/messages/{id} returns appropriate error when authenticated but message not found."""
        # Mock Gmail client to avoid actual API calls
        with patch("src.clients.gmail_client.build_gmail_service"), \
             patch("src.clients.gmail_client.trash_message"):
            response = authenticated_client.delete("/api/messages/nonexistent-id")
            # Should return 200 with deleted=False (not 401)
            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] is False

    def test_batch_delete_empty_authenticated(self, authenticated_client):
        """Test DELETE /api/messages/batch with empty list when authenticated."""
        response = authenticated_client.request("DELETE", "/api/messages/batch", json={"ids": []})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 0
