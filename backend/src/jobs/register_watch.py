#!/usr/bin/env python3
"""Register a Gmail watch to a Pub/Sub topic using OAuth credentials from env.

This version lives inside the `src` package and uses relative imports so it can
be executed as a module (python -m src.register_watch) when run from the
`backend` directory.
"""
import os
import sys
import json
from datetime import datetime, timezone
from ..clients.gmail import build_credentials_from_oauth, build_gmail_service, register_watch


def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH")
    topic = os.environ.get("GMAIL_PUBSUB_TOPIC")

    if not all([client_id, client_secret, refresh_token, topic]):
        print("Missing required env vars. Set: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH, GMAIL_PUBSUB_TOPIC")
        sys.exit(1)

    creds = build_credentials_from_oauth(client_id, client_secret, refresh_token)
    service = build_gmail_service(credentials=creds)

    print(f"Registering watch for topic: {topic}")
    resp = register_watch(service, topic)
    print("Watch response:")
    print(resp)

    # Save the watch response to a file in the user's home directory so other
    # scripts (or manual workflows) can pick up the historyId later.
    home = os.path.expanduser("~")
    save_path = os.path.join(home, ".organize_mail_watch.json")
    # Use a timezone-aware UTC timestamp (avoid deprecated utcnow)
    payload = {
        "watch_response": resp,
        # produce an ISO8601 UTC timestamp ending with 'Z'
        "saved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    try:
        with open(save_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"Saved watch response to: {save_path}")
    except OSError as exc:  # pragma: no cover - best-effort save
        print(f"Warning: failed to save watch response to {save_path}: {exc}")


if __name__ == '__main__':
    main()
