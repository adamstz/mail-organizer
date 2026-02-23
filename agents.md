# Agents (Runners and LLM components)

This document explains the "agents" and runtime actors in the repository — the background jobs and LLM-powered components responsible for classifying, embedding, indexing, and answering queries about emails.

Why this exists
- The codebase contains multiple *agents* (long-running or one-off scripts) that operate on email data and call LLMs. This doc helps contributors and operators understand what each agent does, where the code lives, how to run them, and how to add new agents.

Quick links
- LLM classification: `backend/src/services/llm_processor.py`
- RAG (Q&A) engine: `backend/src/services/rag_engine.py`
- Prompt templates: `backend/src/services/prompt_templates.py`
- Background job scripts: `backend/src/jobs/` (classify_all.py, embed_all_emails.py, pull_messages.py, etc.)
- Entry points / CLI: `backend/cli.py`
- **Documentation:** `docs/QUERY_FLOW.md` (complete query pipeline), `docs/RAG_DOC.md` (embeddings/vector setup)

Contents
- Overview
- Agent types and responsibilities
- How to run (local, Docker)
- Environment variables and configuration
- Adding a new agent (developer guide)
- Observability, testing and safety
- Troubleshooting & FAQ

---

## Overview

The project organizes email processing into a few runtime actors:

1. Background jobs - single-run or scheduled scripts that fetch messages, generate embeddings, and classify messages using LLMs.
2. LLM Processors - reusable service classes that abstract calling an LLM provider (OpenAI, Anthropic, Ollama, or an external command) and parsing responses.  See `backend/src/services/llm_processor.py`.
3. RAG Engine - retrieval + generation flow for question-answering over emails. See `backend/src/services/rag_engine.py`.

Notes about the codebase and authoritative source
- The `docs/` directory contains current documentation: `QUERY_FLOW.md` (complete query pipeline) and `RAG_DOC.md` (embedding/vector setup). For implementation details, refer to the actual code in `backend/src/`.

---

## Agent types & responsibilities

### 1) Background jobs (workers)
Location: `backend/src/jobs/`

- `pull_messages.py` / `pull_all_inbox.py` — fetch messages from Gmail API, store them into DB. These scripts are responsible for ingestion.
- `embed_all_emails.py` — batch job to generate embeddings for messages (embedding service).
- `classify_messages.py` / `classify_all.py` — run the classification pipeline (uses the LLM processor).
- `register_watch.py` — register Gmail push watches (if using push notifications).

These scripts are intended to be run manually, by cron, or by orchestration systems (Kubernetes CronJob, runners, etc.). They are plain Python modules you can run with `python -m src.jobs.<name>` from the `backend` directory.

### 2) Cloudflare Postgres Tunnel
File: `backend/cloudflared_postgres.sh`

A utility script that creates a local proxy to a PostgreSQL database protected by Cloudflare Access. This is useful when the database is behind Cloudflare Zero Trust and you need to connect from a local development environment.

Usage:

```bash
# Start tunnel in background
./cloudflared_postgres.sh

# Stop the tunnel
./cloudflared_postgres.sh stop

# Check tunnel status
./cloudflared_postgres.sh status

# Restart the tunnel
./cloudflared_postgres.sh restart
```

Environment variables:
- `CLOUDFLARE_ACCESS_URL` — Required. The Cloudflare Access URL (e.g., `https://db.example.com`)
- `POSTGRES_USER` — PostgreSQL username (default: `postgres`)
- `POSTGRES_DB` — PostgreSQL database name (default: `postgres`)
- `LOCAL_PORT` — Local port to bind the proxy to (default: `5433`)

Once running, connect to the proxied database:

```bash
psql -h localhost -p 5433 -U postgres -d postgres
```

The script manages a PID file at `/tmp/cloudflared_postgres.pid` and logs to `/tmp/cloudflared_postgres.log`.

### 3) LLM Processor
File: `backend/src/services/llm_processor.py`

- Abstracts support for multiple LLM providers and fallbacks:
  - Providers supported: `openai`, `anthropic`, `ollama`, `command` (external command), and `rules` (local keyword-based rules for tests).
  - Implements: detection of provider via environment variables, LangChain integrations where available, provider-specific calls, fallback flows, parsing JSON output, and normalization of classification results.
- The processor is used by the classification jobs and the RAG engine.

Key behaviours and defaults (verify in code):
- Default temperature: 0.3
- Default max tokens: 200
- TIMEOUT: 60s (increased for local/slow models)
- Output parsing: accepts JSON returned in plain text or inside markdown code fences

### 4) RAG Q&A Engine
File: `backend/src/services/rag_engine.py`

- Workflow: user question → classify query type → route to handler → handler processes and returns response.
- Query types supported: conversation, aggregation, search-by-sender, search-by-attachment, classification, temporal, filtered-temporal, semantic, list-previous-results.
- Uses `QueryClassifier` to detect query type, then delegates to specialized handlers in `backend/src/services/query_handlers/`.
- Handlers: `ConversationHandler`, `AggregationHandler`, `SenderHandler`, `AttachmentHandler`, `ClassificationHandler`, `TemporalHandler`, `SemanticHandler`, `PreviousResultsHandler`.
- Each handler uses `ContextBuilder` to format email data and `LLMProcessor` to generate natural language responses.

**Result Caching for Follow-up Queries:**

The RAG engine caches query results to enable follow-up queries like "list those 78 emails":

- **File**: `backend/src/services/result_cache.py`
- **Cache**: In-memory LRU cache (100 sessions max, 30-minute TTL, 500 message IDs per result)
- **Detection**: `QueryClassifier._is_list_previous_request()` detects patterns like "list those", "show them"
- **Handler**: `PreviousResultsHandler` retrieves cached message IDs and fetches full details
- **Structured Types**: `backend/src/models/query_response.py` defines `QueryResponse` Pydantic model with `cached_message_ids` field

**Retrieval Strategy (Industry-Standard Hybrid Search):**

The semantic search handler implements state-of-the-art retrieval combining:

1. **Hybrid Search (Vector + Keyword)**
   - Combines semantic vector search (pgvector) with PostgreSQL full-text search (tsvector/BM25-like)
   - Uses Reciprocal Rank Fusion (RRF) to merge ranked results from both methods
   - Default weights: 50% vector, 50% keyword (balanced for exact keyword matching)
   - Retrieves 50 candidates from each method before fusion

2. **Cross-Encoder Reranking**
   - Reranks top-50 hybrid results using `cross-encoder/ms-marco-MiniLM-L-6-v2`
   - More accurate relevance scoring than bi-encoder embeddings
   - Returns final top-20 results to LLM for answer generation

3. **Full Email Context**
   - Context builder uses full email body (up to 2000 chars per email) instead of snippet
   - Significantly improves LLM answer quality with complete information
   - Auto-truncates long emails to stay within context windows

Implementation files:
- Hybrid search: `backend/src/storage/postgres_storage.py` (methods: `keyword_search`, `hybrid_search`, `list_by_topic`, `get_messages_by_ids`)
- Reranking: `backend/src/services/query_handlers/semantic.py` (method: `_rerank_results`)
- Context assembly: `backend/src/services/context_builder.py` (uses `message.get_body_text()`)
- Result caching: `backend/src/services/result_cache.py` (LRU cache for follow-up queries)
- Structured types: `backend/src/models/query_response.py` (Pydantic model for responses)

---

## How to run (developer / operator quick start)
For complete query processing details, see `docs/QUERY_FLOW.md`. For embeddings and vector search setup, see `docs/RAG_DOC.md`.

Note: If not running in a codespace, source your environment variables from `~/export.sh` before proceeding with the commands below.

### Database Setup for Hybrid Search

**First-time setup:** Run the full-text search migration to enable hybrid retrieval:

```bash
cd backend
python run_migration.py src/storage/migrations/001_add_fulltext_search.sql
```

This adds:
- `search_vector` tsvector column to messages table
- GIN index for fast keyword search
- Automatic trigger to update tsvector on new messages
- Population of existing messages with search vectors

Common run patterns (from the `backend` folder):

- Classify unclassified messages (incremental):

```bash
# activate venv and run
source .venv/bin/activate
python -m src.jobs.classify_all
```

- Force re-classify all messages (useful for testing):

```bash
python -m src.jobs.classify_all --force
```

- Run the embedding job:

```bash
python -m src.jobs.embed_all_emails
```

- Fetch messages from Gmail:

```bash
python -m src.jobs.pull_messages --user <user_email>
# or
python -m src.jobs.pull_all_inbox
```

RAG Q&A endpoint (server)
- The RAG engine is part of the API server (`backend/src/api.py`) and exposed at `POST /api/query`. Start the API server to make RAG queries.

Run server / API examples

- Start the API server (two options):

```bash
# (a) Using the repo CLI helper
python -m cli run-server

# (b) Direct with uvicorn (recommended for development)
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

- Example RAG query (curl):

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What invoices did I receive last month?","top_k":10}' | jq
```

- Start a background classify job via the API's sync endpoint (runs in background manager):

```bash
curl -X POST http://127.0.0.1:8000/api/sync/classify
```

- Logs and real-time debugging:
  - `/api/logs` returns recent logs as JSON
  - Websocket at `/ws/logs` provides real-time stream for live debugging

Docker / Compose
- The repo has a `docker-compose.yml` and a `llm/Dockerfile` — the exact compose configuration may be out-of-date. Prefer to verify the project's top-level `docker-compose.yml` and `backend/Dockerfile` for accurate developer images.

---

## Environment variables and configuration

The `LLMProcessor` reads configuration from environment variables. Key variables:

- `LLM_PROVIDER` — optional; auto-detects provider when not set. Valid values include `openai`, `anthropic`, `ollama`, `command`, or `rules` (rules is a special test fallback).
- `OPENAI_API_KEY` — OpenAI key for `openai` provider
- `ANTHROPIC_API_KEY` — Anthropic key for `anthropic` provider
- `OLLAMA_HOST` — host for Ollama server (default `http://localhost:11434`)
- `ORGANIZE_MAIL_LLM_CMD` — external command to call for `command` provider
- `LLM_MODEL` — override model name (defaults vary by provider)

Authentication variables (for OAuth flow):
- `JWT_SECRET` — **Required.** Secret key for signing JWT tokens. Generate with `openssl rand -hex 32`
- `GOOGLE_CLIENT_ID` — **Required.** OAuth client ID from GCP Console
- `GOOGLE_CLIENT_SECRET` — **Required.** OAuth client secret from GCP Console
- `ALLOWED_EMAIL` — Optional. Restrict authentication to a specific Gmail address (recommended for self-hosted)
- `BACKEND_URL` — Optional. Backend base URL (default: `http://localhost:8000`)
- `FRONTEND_URL` — Optional. Frontend URL for redirects after OAuth (default: `http://localhost:5173`)
- `OAUTH_REDIRECT_URI` — Optional. Override the OAuth callback URL (default: `{BACKEND_URL}/api/auth/callback`)
- `CORS_ORIGINS` — Optional. Comma-separated list of allowed CORS origins (default: includes FRONTEND_URL and localhost variants)
- `SECURE_COOKIES` — Optional. Set to `true` for HTTPS deployments

**OAuth Token Management:**

The system implements intelligent token management to minimize unnecessary OAuth flows:

1. **Token Checking**: Before redirecting to Google OAuth, the `/api/auth/login` endpoint checks for:
   - Valid JWT session cookie AND valid Gmail tokens (if present, redirects immediately to frontend)
   - Valid JWT session but Gmail disconnected (redirects to OAuth to reconnect Gmail)
   - No valid JWT session (always redirects to OAuth for identity verification)

   **Security**: Unauthenticated requests (no JWT cookie) always go through Google OAuth to verify identity. The system never auto-creates sessions from database tokens without verified identity.

2. **Automatic Token Refresh**: When OAuth tokens expire but the user has a valid JWT session, the system automatically uses the refresh token to obtain new access tokens without requiring user interaction. This happens in:
   - `/api/auth/status` — attempts refresh when checking Gmail connection status

3. **Gmail Connection Status**: The `/api/auth/status` endpoint returns:
   - `authenticated`: Whether user has valid JWT session
   - `gmail_connected`: Whether valid OAuth tokens exist (separate from JWT)
   
4. **Force OAuth Flow**: Use `/api/auth/login?force=true` to bypass all checks and go directly to Google OAuth. This is used when reconnecting Gmail after token revocation.

5. **Frontend Reconnection UI**: When `gmail_connected` is false:
   - SyncStatus shows "Gmail: Not Connected" chip in error color
   - Clicking the chip shows a centered login page with "Reconnect Gmail" title
   - User can cancel and return to the app, or proceed to reconnect

6. **Graceful Fallback**: If token refresh fails or no tokens exist, the system falls back to the full OAuth consent flow.

This approach significantly reduces friction for returning users while maintaining security.

Other service variables (used by storage/RAG):
- DB connection details (set in the environment or storage config)
- `PGVECTOR` and `pgvector` extension — required for RAG/embedding search in Postgres

For complete configuration details and query pipeline documentation, see `docs/QUERY_FLOW.md`.
For authentication setup details, see `docs/AUTH_IMPLEMENTATION_PLAN.md`.

Provider examples (copy/paste)

```bash
# OpenAI (preferred when using OpenAI API)
export OPENAI_API_KEY="sk_..."
export LLM_PROVIDER=openai   # optional - detection also works

# Anthropic (Claude)
export ANTHROPIC_API_KEY="anthropic_..."
export LLM_PROVIDER=anthropic

# Ollama local server
export OLLAMA_HOST="http://localhost:11434"
export LLM_PROVIDER=ollama

# External command provider: command should accept JSON on stdin with {subject, body}
# and print JSON classification to stdout. Example: ORGANIZE_MAIL_LLM_CMD="/usr/local/bin/my_llm_cli"
export ORGANIZE_MAIL_LLM_CMD="/usr/local/bin/my_llm_cli"
export LLM_PROVIDER=command

# Test / local rule-based provider (no network calls)
export LLM_PROVIDER=rules

# Optional: override the model name
export LLM_MODEL="gpt-4"  # or "claude-3-haiku" / "llama3" depending on provider
```

Notes:
- `command` provider expects the external program to accept a JSON object `{"subject":"..","body":".."}` as stdin and produce a JSON output matching the classification schema (labels, priority, summary).
- `rules` is a test-only fallback that uses keyword matching in code; it is intentionally limited and not intended for production.

---

## Add a new agent (developer guide)
If you need to add a new agent (background job or runner), follow these conventions:

1. Location: Add the script to `backend/src/jobs/`.
2. Naming: Use clear names like `do_something.py` with `#!/usr/bin/env python3` and a `main()` block.
3. CLI: Use argparse for options like `--limit`, `--force`.
4. Reuse existing services: Import `LLMProcessor`, `EmbeddingService`, etc., from `backend/src/services/`.
5. Logging, idempotency, tests: Use logging, handle errors, make scripts idempotent, add unit/integration tests.

Example skeleton (copy into `backend/src/jobs/my_agent.py`):

```python
#!/usr/bin/env python3
import argparse
from .. import storage
from ..services import LLMProcessor

def main():
    storage.init_db()
    processor = LLMProcessor()
    # Process items...

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    main()
```

Best practices: Keep agents small and focused, reuse shared services, make idempotent, add tests.

---

## Observability, testing and safety

- Logging: Jobs should produce human-readable logs. The LLMProcessor and RAG engine include `logger.info/debug` calls for major steps.
- Timeouts and retries: LLM timeouts are configured in `LLMProcessor.TIMEOUT` (default 60s). Jobs should handle exceptions and optionally retry transient problems.
- Privacy: embeddings are created locally by default (see `docs/RAG_DOC.md`). Avoid sending raw emails to external models unless intentionally configured via provider keys.
- Query Pipeline: See `docs/QUERY_FLOW.md` for complete documentation on classification, handlers, and retrieval strategies.
- Testing: The repo contains unit and integration tests (`backend/tests/`) — add tests for new agents and LLM flows where applicable.
  **Contributor testing expectations:**

  - Tests are required. Any change to code should include tests (unit or integration depending on the scope) that exercise the new or modified behaviour. Tests should live near the code being changed (for example under `backend/tests/unit/` or `backend/tests/integration/`).

  - Run tests locally before creating a pull request. This helps catch regressions early and avoids CI failures. From the repository root you can run the helper Makefile targets (recommended) or use pytest directly. Example Makefile targets in `backend/Makefile`:

```bash
# run lint + all tests (recommended):
make -C backend test

# run unit tests only:
make -C backend test-unit

# run only smoke tests:
make -C backend test-smoke

# run tests with coverage report:
make -C backend test-cov

# a quick watch/iteration mode (requires ptw):
make -C backend test-watch

# formatting and linting helpers you should run before pushing:
make -C backend format
make -C backend lint
```

  If you prefer raw pytest commands they work too, but the Makefile sets appropriate environment values (for example `LLM_PROVIDER=rules` for offline tests) and paths which makes running tests easier and more deterministic.

  - If you make a larger change, run the full test suite (or the relevant integration tests) and fix any regressions before opening the PR. CI runs the full test-suite and will block merges when tests fail.

  - Documentation / markdown-only changes: small changes that only update `*.md` files (documentation, architecture notes, README, `agents.md`, etc.) do not require adding tests or running the test-suite. Still ensure the change is limited to docs and doesn't modify code or configurations — if it touches code, tests are required.

---

## Troubleshooting & FAQ

**Query quality issues:**
- The system now uses hybrid search (vector + keyword) with cross-encoder reranking for better relevance
- If queries still struggle, check:
  - Run the full-text search migration: `python run_migration.py src/storage/migrations/001_add_fulltext_search.sql`
  - Verify search_vector column exists: `SELECT search_vector FROM messages LIMIT 1;`
  - Check cross-encoder loading in logs (should see "Loaded cross-encoder model")
  - Adjust hybrid search weights in semantic handler if needed (currently 60% vector, 40% keyword)

- LLM not configured: Check env vars (`OPENAI_API_KEY`, etc.) or set `LLM_PROVIDER=rules` for testing.
- Ollama issues: Ensure `ollama serve` is running, set `OLLAMA_HOST`, pull models if needed.
- Database / RAG: Confirm pgvector extension and migrations; see `docs/RAG_DOC.md`.
- Timeouts: Default 60s; tune in `LLMProcessor.TIMEOUT` for slow models.
- Classification issues: See `docs/QUERY_FLOW.md` for intent-based classification details and troubleshooting.

Testing: Run with `pytest -q` in `backend/`. Use `LLM_PROVIDER=rules` for unit tests. For CI, mock LLM calls.
