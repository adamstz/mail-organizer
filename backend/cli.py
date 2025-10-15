"""Minimal CLI for running the backend during development.

Usage examples (local dev):

    python -m organize_mail.cli run-server
    python -m organize_mail.cli run-subscriber
"""
import os
import logging
import sys
from importlib import import_module

from .api import app


def run_server():
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


def run_subscriber():
    from .pubsub_subscriber import run_subscriber

    sub = os.environ.get("GMAIL_PUBSUB_SUBSCRIPTION")
    if not sub:
        logging.error("Set GMAIL_PUBSUB_SUBSCRIPTION environment variable")
        sys.exit(2)

    def handler(payload):
        # naive handler: log payload
        logging.info("Received payload: %s", payload)

    run_subscriber(sub, handler)


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
