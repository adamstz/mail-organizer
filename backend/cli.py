"""Minimal CLI for running the backend during development.

Usage examples (local dev):

    python -m cli run-server
    python -m cli run-subscriber
"""
import os
import logging
import sys
from importlib import import_module

from src.api import app


def run_server():
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


def run_subscriber():
    # The Pub/Sub subscriber helper was removed to keep the backend minimal.
    # If you want to consume messages from a subscription, either:
    #  - re-add a subscriber implementation in src.pubsub_subscriber and import it here, or
    #  - run a small one-off script that pulls from the subscription and processes messages.
    logging.error("Pub/Sub subscriber helper not available. Implement 'src.pubsub_subscriber.run_subscriber' or run a custom pull script.")
    sys.exit(2)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__)
        return

    cmd = argv[0]
    if cmd == "run-server":
        run_server()
    elif cmd == "run-subscriber":
        run_subscriber()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
