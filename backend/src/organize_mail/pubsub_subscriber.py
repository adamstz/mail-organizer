"""Stub: Pub/Sub subscriber for Gmail push notifications.

This module provides a small wrapper to run a streaming pull subscriber and
dispatch Gmail push payloads to the processing pipeline.
"""
import os
import json
import logging
from typing import Callable

from google.cloud import pubsub_v1


def run_subscriber(subscription_path: str, handler: Callable[[dict], None]):
    """Start a streaming pull and call handler(payload) for each message.

    subscription_path should be the full resource name, e.g.
    "projects/PROJECT/subscriptions/SUB".
    """
    subscriber = pubsub_v1.SubscriberClient()

    def _callback(message: pubsub_v1.subscriber.message.Message):
        try:
            data = message.data.decode("utf-8")
            payload = json.loads(data)
        except Exception:
            logging.exception("Failed to decode Pub/Sub message")
            message.nack()
            return

        try:
            handler(payload)
            message.ack()
        except Exception:
            logging.exception("Handler raised, nack message")
            message.nack()

    streaming = subscriber.subscribe(subscription_path, callback=_callback)
    logging.info("Listening on %s", subscription_path)
    try:
        streaming.result()
    except KeyboardInterrupt:
        streaming.cancel()

