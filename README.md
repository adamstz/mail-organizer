# organize-mail

AI-powered email organization system with intelligent classification, RAG-powered chat, and multi-provider LLM support.

## Overview

Organize Mail is a full-stack application that helps you manage your inbox intelligently. It uses AI to automatically classify emails, provides a conversational interface to search through your email history, and offers real-time monitoring of classification activities.

<!-- TODO: Add demo.gif or screenshot here -->
![Demo](docs/app.png)
*Application demo showing email classification and chat interface*

## Key Features

- **Intelligent Email Classification**: Automatically categorize emails by type (finance, security, meetings, etc.) and priority
- **RAG-Powered Chat**: Ask questions about your email history using retrieval-augmented generation
- **Real-Time Logging**: WebSocket-based log viewer for monitoring system activity
- **Multi-Provider LLM Support**: Choose from OpenAI, Anthropic, Ollama (local), custom commands, or rule-based classification
- **Gmail Integration**: Pull messages via Gmail API with batch sync (OAuth + refresh token)
- **Flexible Storage**: SQLite or PostgreSQL backend with classification history and audit trails
- **REST API**: FastAPI backend with comprehensive endpoints for messages, classifications, and RAG queries
- **Modern Frontend**: React + TypeScript UI with Material-UI components, resizable panels, and real-time updates

## Project Structure

```
organize-mail/
├── backend/                 # Python FastAPI backend
│   ├── src/
│   │   ├── api.py          # REST API endpoints
│   │   ├── clients/        # Gmail API client
│   │   ├── jobs/           # Background jobs (classification, sync)
│   │   ├── models/         # Data models (Message, ClassificationRecord)
│   │   ├── services/       # LLM processor, RAG engine, query handlers
│   │   ├── storage/        # Storage layer (SQLite, PostgreSQL)
│   │   └── utils/          # HTML/CSS sanitizers, email processing
│   └── tests/              # Pytest test suite
├── frontend/               # React + TypeScript UI
│   ├── src/
│   │   ├── components/     # React components (EmailList, etc.)
│   │   └── types/          # TypeScript type definitions
│   └── tests/              # Vitest test suite
├── llm/                    # Local LLM deployment (Ollama configs)
└── docs/                   # Architecture & runbooks
```

## Quick Start

### Option A: Docker (recommended)

Both services run hot-reloading dev servers in containers — no Python/Node setup on the host, and a single combined log stream.

1. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `JWT_SECRET` (see [Authentication Setup](#authentication-setup) for how to get OAuth credentials). SQLite is the default storage backend and needs no further configuration.

2. **Start everything**
   ```bash
   docker compose up --build
   ```
   This builds and runs the backend (http://localhost:8000) and frontend (http://localhost:5173). Both containers mount the source code from the host, so edits trigger hot reload with no rebuild needed. The database schema is created automatically on first start.

3. **Tail logs**
   ```bash
   docker compose logs -f
   ```
   Both services' output streams to one place — handy for debugging, and a single, greppable target if you're using an AI assistant (e.g. Claude Code) to help diagnose an issue. Append `backend` or `frontend` to follow just one service.

4. **Configure Gmail Integration** — see [Authentication Setup](#authentication-setup).

Stop with `docker compose down`. The SQLite file lives on the host at `backend/mail.db` and persists across restarts.

> **Note:** the backend container reads its config straight from `.env` (via Compose's `env_file:`), not from your shell's exported variables — so it's safe to use Docker even if you also export `STORAGE_BACKEND`, `JWT_SECRET`, etc. natively (e.g. for [native dev](#option-b-run-natively-without-docker)). Whatever's in `.env` is what the container gets.

### Option B: Run natively (without Docker)

**Backend** (one-time, requires Python 3):
```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ..
```

**Frontend & root deps** (one-time):
```bash
npm run setup
```

**Set environment variables** — SQLite is recommended for local development (no Postgres needed):
```bash
export STORAGE_BACKEND=sqlite          # use SQLite for local dev
export STORAGE_DB_PATH=./mail.db       # optional — defaults to ~/.organize_mail.db
export JWT_SECRET=$(openssl rand -hex 32)
export GOOGLE_CLIENT_ID="your_client_id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your_client_secret"
```

**Start both servers**:
```bash
npm run dev
```

This starts the FastAPI backend on http://localhost:8000 and the Vite frontend on http://localhost:5173 in a single terminal with labeled, color-coded output. The database schema is created automatically on first start — no migration scripts needed.

Then configure Gmail Integration — see [Authentication Setup](#authentication-setup).

See [Backend README](backend/README.md) and [Frontend README](frontend/README.md) for detailed setup instructions.

## Authentication Setup

The application uses OAuth 2.0 to access your Gmail. Follow these steps:

### 1. Create Google OAuth Credentials

1. Go to [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing one
3. Enable the **Gmail API**
4. Create OAuth 2.0 Client ID (Web application type)
5. Add authorized redirect URI: `http://localhost:8000/api/auth/callback`

### 2. Set Environment Variables

**Docker** — set these in `.env` (created from `.env.example`, see [Quick Start](#quick-start)):
```bash
JWT_SECRET=...           # generate with: openssl rand -hex 32
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
STORAGE_BACKEND=sqlite    # or 'postgres' for production

# Optional - restrict to your email only (recommended for self-hosted)
ALLOWED_EMAIL=your.email@gmail.com

# Optional - set to 'true' when running behind HTTPS (see note below)
SECURE_COOKIES=false
```

**Native (no Docker)** — export the same values in your shell:
```bash
export JWT_SECRET=$(openssl rand -hex 32)
export GOOGLE_CLIENT_ID="your_client_id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your_client_secret"
export STORAGE_BACKEND=sqlite   # or 'postgres' for production

# Optional - restrict to your email only (recommended for self-hosted)
export ALLOWED_EMAIL="your.email@gmail.com"
```

> **`SECURE_COOKIES`**: When set to `true`, the browser will only send authentication and CSRF-protection cookies over HTTPS connections. This prevents session hijacking over plain HTTP, and should be enabled whenever the app is exposed beyond localhost (e.g. behind a reverse proxy with TLS). Leave it `false` for local development — `localhost` doesn't use HTTPS so `Secure` cookies would break login entirely.

### 3. Authenticate

1. Start the backend and frontend servers (`docker compose up --build`, or `npm run dev` if running natively)
2. Open http://localhost:5173
3. Click "Sign in with Google"
4. Grant Gmail read permissions

> The database schema (including the OAuth tokens table) is created automatically on first start. No migration scripts are needed for a fresh install.

For detailed documentation, see [docs/AUTH_IMPLEMENTATION_PLAN.md](docs/AUTH_IMPLEMENTATION_PLAN.md).

## TODO

- [x] **OAuth Integration**: Migrate from manual refresh token to proper OAuth flow
- [ ] **Gmail Pub/Sub**: Add real-time email notifications via Gmail Pub/Sub webhooks

## Documentation

- [Backend README](backend/README.md) - API, jobs, storage, and RAG details
- [Frontend README](frontend/README.md) - UI components, logging, and development
- [Agents & LLM Components](agents.md) - Background jobs, LLM processors, and RAG engine
- [Query Flow](docs/QUERY_FLOW.md) - Complete query pipeline and classification
- [RAG Documentation](docs/RAG_DOC.md) - Retrieval-augmented generation system
- [Storage Schema](docs/STORAGE_SCHEMA.md) - Database schema and migrations

## License

See [LICENSE](LICENSE)
