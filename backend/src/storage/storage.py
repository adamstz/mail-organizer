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

    def init_db(self) -> None:
        self._messages.clear()
        self._meta.clear()

    def save_message(self, msg: MailMessage) -> None:
        self._messages[msg.id] = msg

    def get_message_ids(self) -> List[str]:
        return list(self._messages.keys())

    def list_messages(self, limit: int = 100) -> List[MailMessage]:
        return list(self._messages.values())[:limit]

    def get_history_id(self) -> Optional[str]:
        return self._meta.get("historyId")

    def set_history_id(self, history_id: str) -> None:
        self._meta["historyId"] = history_id


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


def list_messages(limit: int = 100) -> List[MailMessage]:
    return _backend.list_messages(limit=limit)


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
