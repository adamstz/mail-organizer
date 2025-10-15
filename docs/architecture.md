# Architecture

Overview:

- Gmail sends push notifications to a Pub/Sub topic.
- The backend runs a Pub/Sub subscriber or accepts push requests to fetch message history from Gmail API.
- Messages are fetched and passed to the local LLM service for categorization and enrichment.
- Results are persisted (DB TBD) and surfaced to the React frontend.

Components to implement:

- Auth: Gmail OAuth for user-level access; service account with Pub/Sub permissions.
- Storage: small DB (SQLite/Postgres) to store message metadata and labels.
- LLM: local model server exposing a simple HTTP API.
- Frontend: React app to browse messages and labels.
