"""Pluggable storage shim that delegates to a chosen backend implementation.

The module preserves the previous function names but forwards calls to the
configured backend. The default backend is SQLite (sqlite_storage.SQLiteStorage).
To swap backends at runtime call `set_storage_backend()` with an object that
implements the StorageBackend interface (see storage_interface.py).
"""
from __future__ import annotations

from typing import List, Optional

from ..models.message import MailMessage
from .storage_interface import StorageBackend
from .sqlite_storage import SQLiteStorage
from .sqlite_storage import default_db_path
import os


# in-memory backend for testing
class InMemoryStorage(StorageBackend):
    def __init__(self):
        self._messages: dict[str, MailMessage] = {}
        self._meta: dict[str, str] = {}
        # store classification records in memory for tests/dev
        self._classifications: dict[str, list[dict]] = {}
        self._latest_classification: dict[str, str] = {}  # message_id -> classification_id

    def init_db(self) -> None:
        self._messages.clear()
        self._meta.clear()
        self._classifications.clear()
        self._latest_classification.clear()

    def save_message(self, msg: MailMessage) -> None:
        self._messages[msg.id] = msg

    def save_classification_record(self, record) -> None:
        lst = self._classifications.setdefault(record.message_id, [])
        lst.append(record.to_dict())
    
    def create_classification(self, message_id: str, labels: List[str], priority: str, summary: str, model: str = None) -> str:
        """Create a new classification record and link it to the message."""
        import uuid
        from datetime import datetime, timezone
        
        classification_id = str(uuid.uuid4())
        classification = {
            "id": classification_id,
            "message_id": message_id,
            "labels": labels,
            "priority": priority,
            "summary": summary,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Store classification
        lst = self._classifications.setdefault(message_id, [])
        lst.append(classification)
        
        # Update message's latest classification reference
        self._latest_classification[message_id] = classification_id
        
        # Also update the message object if it exists
        if message_id in self._messages:
            msg = self._messages[message_id]
            msg.classification_labels = labels
            msg.priority = priority
            msg.summary = summary
        
        return classification_id
    
    def get_latest_classification(self, message_id: str) -> Optional[dict]:
        """Get the most recent classification for a message."""
        classification_id = self._latest_classification.get(message_id)
        if not classification_id:
            return None
        
        # Find the classification in the list
        for classification in self._classifications.get(message_id, []):
            if classification["id"] == classification_id:
                return classification
        
        return None

    def get_message_ids(self) -> List[str]:
        return list(self._messages.keys())
    
    def get_message_by_id(self, message_id: str) -> Optional[MailMessage]:
        """Get a single message by ID."""
        return self._messages.get(message_id)
    
    def get_unclassified_message_ids(self) -> List[str]:
        """Get IDs of messages that haven't been classified yet."""
        return [
            msg_id for msg_id in self._messages.keys()
            if msg_id not in self._latest_classification
        ]
    
    def count_classified_messages(self) -> int:
        """Count how many messages have been classified."""
        return len(self._latest_classification)

    def list_messages(self, limit: int = 100, offset: int = 0) -> List[MailMessage]:
        return list(self._messages.values())[offset:offset+limit]

    def get_history_id(self) -> Optional[str]:
        return self._meta.get("historyId")

    def set_history_id(self, history_id: str) -> None:
        self._meta["historyId"] = history_id

    def list_classification_records_for_message(self, message_id: str):
        data = self._classifications.get(message_id, [])
        from ..models.classification_record import ClassificationRecord
        out = []
        for d in data:
            out.append(ClassificationRecord.from_dict(d))
        return out

def storage_factory_from_env() -> StorageBackend:
    """Create a storage backend instance based on STORAGE_BACKEND env var.

    Supported values:
      - sqlite (default)
      - memory
    """
    mode = os.environ.get("STORAGE_BACKEND", "sqlite").lower()
    if mode == "memory" or mode == "inmemory":
        return InMemoryStorage()
    # default: sqlite
    db_path = os.environ.get("STORAGE_DB_PATH") or default_db_path()
    return SQLiteStorage(db_path=db_path)


# default backend instance
_backend: StorageBackend = storage_factory_from_env()


def set_storage_backend(backend: StorageBackend) -> None:
    global _backend
    _backend = backend


def get_storage_backend() -> StorageBackend:
    return _backend


def init_db() -> None:
    _backend.init_db()


def save_message(msg: MailMessage) -> None:
    _backend.save_message(msg)


def get_message_ids() -> List[str]:
    return _backend.get_message_ids()


def get_message_by_id(message_id: str) -> Optional[MailMessage]:
    """Get a single message by ID."""
    return _backend.get_message_by_id(message_id)


def get_unclassified_message_ids() -> List[str]:
    """Get IDs of messages that haven't been classified yet."""
    return _backend.get_unclassified_message_ids()


def count_classified_messages() -> int:
    """Count how many messages have been classified."""
    return _backend.count_classified_messages()


def list_messages(limit: int = 100, offset: int = 0) -> List[MailMessage]:
    return _backend.list_messages(limit=limit, offset=offset)


def create_classification(message_id: str, labels: List[str], priority: str, summary: str, model: str = None) -> str:
    """Create a new classification and link it to a message.
    
    Returns the classification ID.
    """
    return _backend.create_classification(message_id, labels, priority, summary, model)


def get_latest_classification(message_id: str) -> Optional[dict]:
    """Get the most recent classification for a message.
    
    Returns dict with: id, labels, priority, summary, model, created_at
    """
    return _backend.get_latest_classification(message_id)


def save_classification_record(record) -> None:
    _backend.save_classification_record(record)


def list_classification_records_for_message(message_id: str):
    return _backend.list_classification_records_for_message(message_id)


def list_messages_dicts(limit: int = 100, offset: int = 0) -> List[dict]:
    """Return serializable dicts for messages suitable for JSON responses.

    This acts like a small stored-procedure helper for the API layer.
    """
    msgs = _backend.list_messages(limit=limit)
    dicts: List[dict] = []
    for m in msgs[offset:]:
        d = m.to_dict()
        dicts.append(d)
    return dicts


def get_history_id() -> Optional[str]:
    return _backend.get_history_id()


def set_history_id(history_id: str) -> None:
    _backend.set_history_id(history_id)
