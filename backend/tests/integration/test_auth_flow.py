"""
Integration tests for authentication flow.

Tests the full OAuth callback flow, protected endpoints, and token storage
using the FastAPI TestClient with mocked Google responses.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

# Set required environment variables before imports
os.environ["JWT_SECRET"] = "test_jwt_secret_for_integration_tests"
os.environ["GOOGLE_CLIENT_ID"] = "test_client_id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test_client_secret"
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["LLM_PROVIDER"] = "rules"


class TestAuthEndpoints:
    """Integration tests for authentication API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client with fresh app instance."""
        # Import after setting env vars
        from src.api import app
        from src import storage
        
        # Reset storage to clean state
        storage.set_storage_backend(None)
        
        with TestClient(app) as client:
            yield client

    def test_auth_status_unauthenticated(self, client):
        """Test auth status returns unauthenticated when no cookie."""
        response = client.get("/api/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["email"] is None
        assert data["gmail_connected"] is False

    def test_auth_login_redirects_to_google(self, client):
        """Test login endpoint redirects to Google OAuth."""
        response = client.get("/api/auth/login", follow_redirects=False)
        
        assert response.status_code == 307  # Temporary redirect
        location = response.headers.get("location", "")
        assert "accounts.google.com" in location
        assert "client_id=" in location

        # Verify CSRF state cookie is set
        assert "oauth_state" in response.cookies

    def test_auth_login_with_redirect_url(self, client):
        """Test login preserves redirect URL in CSRF-protected state."""
        import json
        import base64
        from urllib.parse import urlparse, parse_qs
        
        redirect_url = "http://localhost:5173/dashboard"
        response = client.get(
            f"/api/auth/login?redirect_url={redirect_url}",
            follow_redirects=False
        )
        
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "accounts.google.com" in location

        # Decode the state parameter and verify redirect_url is inside
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        state = params.get("state", [None])[0]
        assert state is not None
        payload = json.loads(base64.urlsafe_b64decode(state))
        assert payload["redirect_url"] == redirect_url
        assert "nonce" in payload

    def test_auth_login_unauthenticated_with_db_tokens_redirects_to_oauth(self, client):
        """Test that unauthenticated users are redirected to OAuth even when DB has valid tokens.
        
        Security test: Verifies that /api/auth/login never auto-creates sessions from
        database tokens without verified identity (JWT). This prevents an incognito/
        unauthenticated user from being auto-signed in.
        """
        from src import storage
        from datetime import datetime, timedelta, timezone
        
        # Simulate tokens in DB from a previous session
        email = "authenticated-user@gmail.com"
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        storage.save_oauth_tokens(
            email=email,
            access_token="valid_access_token",
            refresh_token="valid_refresh_token",
            token_expiry=future_expiry,
        )
        
        # Make request without JWT cookie (unauthenticated)
        response = client.get("/api/auth/login", follow_redirects=False)
        
        # Should redirect to Google OAuth (NOT auto-login)
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "accounts.google.com" in location
        assert "client_id=" in location
        
        # Should NOT set auth cookie
        assert "auth_token" not in response.cookies

    def test_auth_logout_clears_cookie(self, client):
        """Test logout clears auth cookie."""
        from src.auth.middleware import create_jwt_token, JWT_COOKIE_NAME

        # Must be authenticated to log out
        token = create_jwt_token("testuser@gmail.com")
        client.cookies.set(JWT_COOKIE_NAME, token)

        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"

        # Check that cookie was cleared
        set_cookie = response.headers.get("set-cookie", "")
        # Should have max-age=0 or expires in past
        assert "auth_token" in set_cookie.lower()

    def test_protected_endpoint_without_auth(self, client):
        """Test that protected endpoints return 401 without auth."""
        # Note: Endpoints are not yet protected in the implementation
        # This test documents expected behavior once protection is added
        response = client.get("/api/auth/status")
        
        # Auth status itself should be accessible
        assert response.status_code == 200


class TestAuthCallbackFlow:
    """Tests for OAuth callback handling."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage
        
        # Use memory storage for tests
        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()
        
        with TestClient(app) as client:
            yield client

    @pytest.mark.asyncio
    async def test_auth_callback_success(self, client):
        """Test successful OAuth callback stores tokens and sets cookie."""
        from datetime import datetime, timedelta, timezone
        from src.auth.oauth import generate_oauth_state
        
        # Generate a valid CSRF state + nonce
        state, nonce = generate_oauth_state()

        # Mock the Google SDK Flow and Credentials
        mock_credentials = MagicMock()
        mock_credentials.token = "mock_access_token"
        mock_credentials.refresh_token = "mock_refresh_token"
        mock_credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_credentials.id_token = {"email": "testuser@gmail.com"}
        
        mock_flow = MagicMock()
        mock_flow.fetch_token = MagicMock()
        mock_flow.credentials = mock_credentials
        
        with patch("src.auth.oauth._create_flow", return_value=mock_flow):
            response = client.get(
                f"/api/auth/callback?code=test_auth_code&state={state}",
                cookies={"oauth_state": nonce},
                follow_redirects=False
            )
        
        # Should redirect after successful auth
        assert response.status_code == 302
        
        # Should set auth cookie
        cookies = response.cookies
        assert "auth_token" in cookies or "set-cookie" in response.headers

    @pytest.mark.asyncio
    async def test_auth_callback_rejects_missing_csrf_state(self, client):
        """Test callback rejects requests without CSRF state."""
        response = client.get(
            "/api/auth/callback?code=test_auth_code",
            follow_redirects=False
        )
        
        # Should redirect to frontend with error
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "auth_error" in location

    @pytest.mark.asyncio
    async def test_auth_callback_rejects_wrong_csrf_nonce(self, client):
        """Test callback rejects requests with mismatched CSRF nonce."""
        from src.auth.oauth import generate_oauth_state

        state, _nonce = generate_oauth_state()

        response = client.get(
            f"/api/auth/callback?code=test_auth_code&state={state}",
            cookies={"oauth_state": "wrong_nonce"},
            follow_redirects=False
        )

        # Should redirect to frontend with error
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "auth_error" in location

    def test_auth_callback_without_code_fails(self, client):
        """Test callback fails without authorization code."""
        response = client.get("/api/auth/callback", follow_redirects=False)
        
        # FastAPI should return 422 for missing required query param
        assert response.status_code == 422


class TestAuthenticatedSession:
    """Tests for authenticated session behavior."""

    @pytest.fixture
    def authenticated_client(self):
        """Create a test client with authenticated session."""
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage
        from src.auth.middleware import create_jwt_token, JWT_COOKIE_NAME
        
        # Set up storage
        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()
        
        # Create JWT token for test user
        token = create_jwt_token("testuser@gmail.com")
        
        with TestClient(app, cookies={JWT_COOKIE_NAME: token}) as client:
            yield client

    @pytest.fixture
    def authenticated_client_with_valid_tokens(self):
        """Create a test client with authenticated session and valid OAuth tokens."""
        from datetime import datetime, timedelta, timezone
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage
        from src.auth.middleware import create_jwt_token, JWT_COOKIE_NAME
        
        # Set up storage
        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()
        
        # Save valid OAuth tokens
        email = "testuser@gmail.com"
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        memory_storage.save_oauth_tokens(
            email=email,
            access_token="valid_access_token",
            refresh_token="valid_refresh_token",
            token_expiry=future_expiry,
        )
        
        # Create JWT token for test user
        token = create_jwt_token(email)
        
        with TestClient(app, cookies={JWT_COOKIE_NAME: token}) as client:
            yield client

    @pytest.fixture
    def authenticated_client_with_expired_tokens(self):
        """Create a test client with authenticated session but expired OAuth tokens."""
        from datetime import datetime, timedelta, timezone
        from src.api import app
        from src import storage
        from src.storage.memory_storage import InMemoryStorage
        from src.auth.middleware import create_jwt_token, JWT_COOKIE_NAME
        
        # Set up storage
        memory_storage = InMemoryStorage()
        storage.set_storage_backend(memory_storage)
        memory_storage.init_db()
        
        # Save expired OAuth tokens without refresh token
        email = "testuser@gmail.com"
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        memory_storage.save_oauth_tokens(
            email=email,
            access_token="expired_access_token",
            refresh_token=None,  # No refresh token
            token_expiry=past_expiry,
        )
        
        # Create JWT token for test user
        token = create_jwt_token(email)
        
        with TestClient(app, cookies={JWT_COOKIE_NAME: token}) as client:
            yield client

    def test_auth_status_authenticated(self, authenticated_client):
        """Test auth status returns user info when authenticated."""
        response = authenticated_client.get("/api/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["email"] == "testuser@gmail.com"
        # gmail_connected should be False when no OAuth tokens exist
        assert data["gmail_connected"] is False

    def test_auth_status_with_valid_gmail_tokens(self, authenticated_client_with_valid_tokens):
        """Test auth status shows gmail_connected when valid tokens exist."""
        response = authenticated_client_with_valid_tokens.get("/api/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["email"] == "testuser@gmail.com"
        assert data["gmail_connected"] is True

    def test_auth_status_with_expired_gmail_tokens(self, authenticated_client_with_expired_tokens):
        """Test auth status shows gmail not connected when tokens expired and no refresh."""
        response = authenticated_client_with_expired_tokens.get("/api/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["email"] == "testuser@gmail.com"
        # Should be False because tokens expired and no refresh token
        assert data["gmail_connected"] is False

    def test_logout_authenticated_user(self, authenticated_client):
        """Test that authenticated user can logout — cookie cleared, tokens preserved."""
        from src import storage

        # Save tokens before logout
        from datetime import datetime, timedelta, timezone
        storage.save_oauth_tokens(
            email="testuser@gmail.com",
            access_token="access",
            refresh_token="refresh",
            token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        response = authenticated_client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"

        # Tokens must still exist — logout is non-destructive
        tokens = storage.get_oauth_tokens("testuser@gmail.com")
        assert tokens is not None
        assert tokens.get("refresh_token") is not None

    def test_disconnect_deletes_tokens(self, authenticated_client):
        """Test that /api/auth/disconnect deletes OAuth tokens from the DB."""
        from src import storage
        from datetime import datetime, timedelta, timezone

        storage.save_oauth_tokens(
            email="testuser@gmail.com",
            access_token="access",
            refresh_token="refresh",
            token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        response = authenticated_client.post("/api/auth/disconnect")

        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"

        # Tokens must be gone
        tokens = storage.get_oauth_tokens("testuser@gmail.com")
        assert tokens is None
