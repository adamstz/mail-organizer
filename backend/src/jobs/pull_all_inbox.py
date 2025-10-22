#!/usr/bin/env python3
"""Pull all messages from the user's INBOX (not incremental).

This is intended for a one-time/full sync. For ongoing incremental
processing you should use the history API + Pub/Sub watch (see register_watch
and pull_messages). After completing a full sync you can call this script
with --save-history to write the current historyId (from users.getProfile)
to ~/.organize_mail_watch.json so future runs can be incremental.

Run as:
  cd backend
  python -m src.pull_all_inbox --limit 100 --workers 8 --save-history

Warnings:
- Full mailbox synces can be slow and consume API quota. Prefer history API
  for production incremental syncs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional

from ..clients.gmail import (
    build_credentials_from_oauth,
    build_gmail_service,
    fetch_message,
)
from ..models.message import MailMessage
from .. import storage


def list_all_message_ids(service, user_id: str = "me", label_ids: Optional[List[str]] = None, q: Optional[str] = None) -> List[str]:
    """Return all message IDs in the mailbox (or filtered by labels/query)."""
    ids: List[str] = []
    messages_resource = service.users().messages()
    request = messages_resource.list(userId=user_id, labelIds=label_ids, q=q, maxResults=500)
    while request is not None:
        resp = request.execute()
        for m in resp.get("messages", []):
            mid = m.get("id")
            if mid:
                ids.append(mid)
        request = messages_resource.list_next(request, resp)
    return ids


def fetch_messages_parallel(service, msg_ids: List[str], max_workers: int = 8, fmt: str = "full") -> List[dict]:
    """Fetch messages in parallel using ThreadPoolExecutor."""
    results: List[dict] = []
    def _get(mid: str) -> dict:
        return fetch_message(service, mid, format=fmt)

    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_get, mid): mid for mid in msg_ids}
        for fut in as_completed(futures):
            mid = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:
                # don't abort whole run on single-message failure
                print(f"Failed to fetch {mid}: {exc}", file=sys.stderr)
    return results


def message_summary(msg: dict) -> MailMessage:
    # Convert raw API message dict to a MailMessage object
    return MailMessage.from_api_message(msg, include_payload=False)


def save_history_id(path: str, history_id: str) -> None:
    payload = {"watch_response": {"historyId": history_id}, "saved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"Saved historyId to {path}")
    except OSError as exc:
        print(f"Warning: failed to save historyId to {path}: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Full sync: pull all messages from INBOX")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of messages fetched (0 = no limit)")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers for fetching")
    parser.add_argument("--save-history", action="store_true", help="After sync, save current historyId to ~/.organize_mail_watch.json")
    parser.add_argument("--format", choices=("full", "metadata", "minimal", "raw"), default="metadata", help="Message format to fetch (default: metadata)")
    args = parser.parse_args()

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH")

    if not all([client_id, client_secret, refresh_token]):
        print("Missing required env vars. Set: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH")
        sys.exit(1)

    creds = build_credentials_from_oauth(client_id, client_secret, refresh_token)
    service = build_gmail_service(credentials=creds)

    # ensure DB exists
    storage.init_db()
    existing_ids = set(storage.get_message_ids())

    print("Listing message IDs in INBOX (may take a while)...")
    all_ids = list_all_message_ids(service, label_ids=["INBOX"])
    total = len(all_ids)
    print(f"Found {total} message IDs in INBOX")

    if args.limit > 0:
        ids_to_fetch = all_ids[: args.limit]
    else:
        ids_to_fetch = all_ids

    if not ids_to_fetch:
        print("No messages to fetch.")
        return

    # skip any IDs already stored in DB
    ids_to_fetch = [mid for mid in ids_to_fetch if mid not in existing_ids]
    print(f"Fetching {len(ids_to_fetch)} messages with {args.workers} workers (format={args.format})...")
    messages = fetch_messages_parallel(service, ids_to_fetch, max_workers=args.workers, fmt=args.format)

    mail_objs = [message_summary(m) for m in messages]
    for m in mail_objs:
        storage.save_message(m)

    summaries = [m.to_dict() for m in mail_objs]
    print(json.dumps(summaries, indent=2))

    if args.save_history:
        # Get current profile to obtain a historyId to use for future incremental syncs
        profile = service.users().getProfile(userId="me").execute()
        history_id = profile.get("historyId")
        if history_id:
            # save historyId to DB metadata for later incremental pulls
            storage.set_history_id(history_id)
        else:
            print("Warning: users.getProfile did not return a historyId")


if __name__ == "__main__":
    main()
