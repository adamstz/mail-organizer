# Authentication Implementation Plan

This document outlines the self-hosted Gmail OAuth authentication flow for the mail-organizer application.

## Overview

A minimal OAuth 2.0 flow for single-user self-hosted deployment. The user authenticates with Google, and the app stores tokens for that Gmail account. No multi-user abstraction needed—the authenticated Gmail address serves as the identity.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│   Google    │
│  (React)    │     │  (FastAPI)  │     │   OAuth     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │   1. Click Login  │                   │
       │──────────────────▶│                   │
       │                   │  2. Redirect to   │
       │                   │     Google        │
       │◀──────────────────│──────────────────▶│
       │                   │                   │
       │   3. User grants  │                   │
       │      consent      │                   │
       │                   │◀──────────────────│
       │                   │  4. Auth code     │
       │                   │     callback      │
       │                   │                   │
       │                   │  5. Exchange code │
       │                   │     for tokens    │
       │                   │──────────────────▶│
       │                   │◀──────────────────│
       │                   │                   │
       │   6. Set JWT      │                   │
       │      cookie       │                   │
       │◀──────────────────│                   │
       │                   │                   │
       │   7. Redirect to  │                   │
       │      app          │                   │
       │◀──────────────────│                   │
```

## Implementation Steps

### Completed

1. **Backend auth module** - Created `backend/src/auth/` with:
   - `oauth.py` - Google OAuth handlers (URL generation, token exchange)
   - `middleware.py` - FastAPI JWT dependencies

2. **Database migration** - Created `backend/src/storage/migrations/004_add_oauth_tokens.sql`:
   - `oauth_tokens` table with columns: `email` (PK), `access_token`, `refresh_token`, `token_expiry`
   - PostgreSQL `pgcrypto` extension for column-level encryption
   - Auto-updating `updated_at` trigger

3. **Storage layer** - Updated `PostgresStorage` and `InMemoryStorage` with:
   - `save_oauth_tokens()` - Store/upsert tokens with encryption
   - `get_oauth_tokens()` - Retrieve decrypted tokens
   - `update_access_token()` - Update access token after refresh
   - `delete_oauth_tokens()` - Remove tokens on logout
   - `get_authenticated_email()` - Get first authenticated user

4. **API endpoints** - Added to `backend/src/api.py`:
   - `GET /api/auth/login` - Redirects to Google consent screen
   - `GET /api/auth/callback` - Handles OAuth code exchange, stores tokens, sets JWT cookie
   - `GET /api/auth/status` - Returns current auth state
   - `POST /api/auth/logout` - Clears JWT cookie and deletes tokens

5. **Gmail client** - Updated `backend/src/clients/gmail_client.py`:
   - `build_credentials_from_db()` - Load credentials from database
   - `get_gmail_credentials()` - Priority: DB → env vars → ADC
   - Automatic token refresh with DB update

6. **Frontend auth flow** - Created:
   - `frontend/src/components/AuthContext.tsx` - React context for auth state
   - `frontend/src/components/LoginPage.tsx` - Login page with Google sign-in button
   - Updated `App.tsx` to wrap with `AuthProvider` and show login when unauthenticated

7. **Tests** - Created:
   - `backend/tests/unit/test_auth_middleware.py` - JWT tests
   - `backend/tests/unit/test_oauth.py` - OAuth flow tests
   - `backend/tests/integration/test_auth_flow.py` - Full flow tests

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `JWT_SECRET` | Secret key for signing JWT tokens | Yes |
| `GOOGLE_CLIENT_ID` | OAuth client ID from GCP Console | Yes |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | Yes |
| `ALLOWED_EMAIL` | Restrict auth to specific Gmail address | Optional |
| `OAUTH_REDIRECT_URI` | Callback URL (default: `http://localhost:8000/api/auth/callback`) | Optional |
| `FRONTEND_URL` | Frontend URL for redirects (default: `http://localhost:5173`) | Optional |
| `SECURE_COOKIES` | Set to "true" for HTTPS deployments | Optional |

## Setup Instructions

### 1. Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing one
3. Enable the Gmail API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Web application"
6. Add authorized redirect URI: `http://localhost:8000/api/auth/callback`
7. Copy the Client ID and Client Secret

### 2. Configure Environment Variables

```bash
# Required
export JWT_SECRET=$(openssl rand -hex 32)
export GOOGLE_CLIENT_ID="your_client_id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your_client_secret"

# Optional - restrict to your email only
export ALLOWED_EMAIL="your.email@gmail.com"

# For production with HTTPS
export SECURE_COOKIES=true
export OAUTH_REDIRECT_URI="https://your-domain.com/api/auth/callback"
export FRONTEND_URL="https://your-domain.com"
```

### 3. Run Database Migration

```bash
cd backend
python run_migration.py src/storage/migrations/004_add_oauth_tokens.sql
```

### 4. Start the Application

```bash
# Backend
cd backend
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev
```

### 5. Authenticate

1. Open http://localhost:5173
2. Click "Sign in with Google"
3. Grant Gmail read permissions
4. You're now authenticated!

## Security Considerations

1. **Token Encryption**: Refresh tokens are encrypted at rest using PostgreSQL's `pgp_sym_encrypt` with the `JWT_SECRET` as the key.

2. **JWT Cookies**: Auth tokens are stored in HTTP-only cookies to prevent XSS attacks.

3. **Email Restriction**: Set `ALLOWED_EMAIL` to prevent unauthorized Google accounts from accessing your instance.

4. **HTTPS**: For production, set `SECURE_COOKIES=true` to ensure cookies are only sent over HTTPS.

## Token Flow

1. **Initial Auth**: User completes OAuth flow → tokens stored encrypted in DB → JWT cookie set
2. **API Requests**: JWT cookie validated → user identity extracted → Gmail client loads tokens from DB
3. **Token Refresh**: When access token expires, Gmail client automatically refreshes and updates DB
4. **Logout**: JWT cookie cleared + tokens deleted from DB

## Files Changed

```
backend/
├── src/
│   ├── auth/
│   │   ├── __init__.py          # Module exports
│   │   ├── middleware.py        # JWT handling
│   │   └── oauth.py             # Google OAuth
│   ├── api.py                   # Auth endpoints
│   ├── clients/
│   │   └── gmail_client.py      # DB token loading
│   └── storage/
│       ├── __init__.py          # Export new functions
│       ├── storage.py           # Shim functions
│       ├── storage_interface.py # Interface methods
│       ├── postgres_storage.py  # Implementation
│       ├── memory_storage.py    # Test implementation
│       └── migrations/
│           └── 004_add_oauth_tokens.sql
├── requirements.txt             # Added PyJWT
└── tests/
    ├── unit/
    │   ├── test_auth_middleware.py
    │   └── test_oauth.py
    └── integration/
        └── test_auth_flow.py

frontend/
└── src/
    ├── App.tsx                  # Auth wrapper
    └── components/
        ├── AuthContext.tsx      # Auth state management
        └── LoginPage.tsx        # Login UI
```

## Future Improvements

1. **Protected Routes**: Add `require_auth` dependency to sensitive endpoints
2. **Token Expiry Warning**: Frontend could check token expiry and prompt re-auth
3. **Multiple Accounts**: Support multiple Gmail accounts (add user_id to messages table)
4. **OAuth Scopes**: Add scope for modifying labels (currently read-only)
