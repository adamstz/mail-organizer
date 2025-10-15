# backend

Python backend using FastAPI. Responsible for:

- Receiving Pub/Sub push messages (or running a subscriber) for Gmail notifications
- Fetching messages via Gmail API
- Passing message content to local LLM processor for categorization and enrichment
- Exposing REST endpoints for the frontend

See `pyproject.toml`, `requirements.txt`, and module stubs.
