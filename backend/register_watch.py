#!/usr/bin/env python3
"""Register a Gmail watch to a Pub/Sub topic using OAuth credentials from env.

Usage:
  export GOOGLE_CLIENT_ID=...
  export GOOGLE_CLIENT_SECRET=...
  export GOOGLE_REFRESH=...
  export GMAIL_PUBSUB_TOPIC=projects/PROJECT_ID/topics/TOPIC_NAME

  python register_watch.py

This script will:
- Build OAuth credentials
- Create a Gmail service
- Call users.watch to register the topic
- Print the watch response (historyId and expiration)

NOTE: The Pub/Sub topic must already exist and have the gmail push service
publisher role:
  serviceAccount:gmail-api-push@system.gserviceaccount.com

"""
import os
import sys
from src.gmail_client import build_credentials_from_oauth, build_gmail_service, register_watch


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


if __name__ == '__main__':
    main()
