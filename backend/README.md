# backend

Python backend using FastAPI. Responsible for:

- Receiving Pub/Sub push messages (or running a subscriber) for Gmail notifications
- Fetching messages via Gmail API
- Passing message content to local LLM processor for categorization and enrichment
- Exposing REST endpoints for the frontend

See `pyproject.toml`, `requirements.txt`, and module stubs.

## Quick Start

### 1. Pull Messages from Gmail
```bash
# Set up Gmail API credentials first:
export GOOGLE_CLIENT_ID="your-client-id"
export GOOGLE_CLIENT_SECRET="your-client-secret"
export GOOGLE_REFRESH="your-refresh-token"

# Pull all messages from INBOX
make pull-inbox

# Or with custom options:
python pull_inbox.py --limit 100 --workers 8
```

### 2. Classify Messages
```bash
make classify          # Classify unclassified messages
make classify-force    # Re-classify all messages

# Or use the script directly:
python classify_all.py --help
python classify_all.py --limit 10    # Test with 10 messages
```

### 3. Running Tests
```bash
make test              # Run all tests
make test-smoke        # Run smoke tests only
make test-cov          # Run tests with coverage
```

### Features
- **Multi-provider LLM support**: OpenAI, Anthropic, Ollama, command, rule-based
- **Smart classification**: Generates labels, priority, and summary for each email
- **Attachment detection**: Tracks which emails have attachments (without downloading them)
- **Progress tracking**: Shows real-time progress with time estimates
- **Skip classified**: Automatically skips already-classified messages
- **Persistent storage**: Stores all data in SQLite database
- **Parallel fetching**: Multi-threaded Gmail API requests for fast syncing

