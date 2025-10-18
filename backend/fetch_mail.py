#!/usr/bin/env python3
"""Simple script to fetch your Gmail messages using OAuth credentials from Codespace secrets.

Usage:
    python fetch_mail.py [--max-results 10]

This script will:
1. Read OAuth credentials from environment variables
2. Authenticate with Gmail API
3. Fetch recent messages
4. Print their subjects and snippets
"""
import os
import sys
import argparse
from src.gmail_client import (
    build_credentials_from_oauth,
    build_gmail_service,
    fetch_message,
)


def main():
    parser = argparse.ArgumentParser(description="Fetch Gmail messages")
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of messages to fetch (default: 10)",
    )
    args = parser.parse_args()

    # Read OAuth credentials from environment variables (Codespace secrets)

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH")
    
    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing required environment variables. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH.")
        sys.exit(1)

    print("Building OAuth credentials...")
    credentials = build_credentials_from_oauth(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    print("Connecting to Gmail API...")
    service = build_gmail_service(credentials=credentials)

    print(f"Fetching up to {args.max_results} recent messages...\n")

    # List messages
    messages_resource = service.users().messages()
    list_response = messages_resource.list(
        userId="me",
        maxResults=args.max_results,
    ).execute()

    messages = list_response.get("messages", [])

    if not messages:
        print("No messages found.")
        return

    print(f"Found {len(messages)} message(s):\n")
    print("=" * 80)

    for i, msg_ref in enumerate(messages, 1):
        msg_id = msg_ref["id"]
        
        # Fetch full message details
        message = fetch_message(service, msg_id, format="metadata")
        
        # Extract headers
        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(No subject)")
        from_addr = headers.get("From", "(Unknown sender)")
        date = headers.get("Date", "(Unknown date)")
        
        print(f"\n{i}. Message ID: {msg_id}")
        print(f"   From: {from_addr}")
        print(f"   Date: {date}")
        print(f"   Subject: {subject}")
        print(f"   Snippet: {message.get('snippet', '')[:100]}...")
        print("-" * 80)

    print(f"\n✓ Successfully fetched {len(messages)} messages!")


if __name__ == "__main__":
    main()
