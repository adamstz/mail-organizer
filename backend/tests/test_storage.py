import os
import tempfile

import pytest

from src.models.message import MailMessage


def test_factory_returns_inmemory_when_env_set(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    from src import storage

    backend = storage.storage_factory_from_env()
    assert type(backend).__name__ == "InMemoryStorage"


def test_inmemory_save_and_get():
    from src.storage import InMemoryStorage

    mem = InMemoryStorage()
    mem.init_db()
    m = MailMessage(id="1", subject="hi", from_="a@b")
    mem.save_message(m)
    ids = mem.get_message_ids()
    assert "1" in ids


def test_sqlite_backend_file(tmp_path):
    from src.storage import SQLiteStorage

    path = str(tmp_path / "test.db")
    s = SQLiteStorage(db_path=path)
    s.init_db()
    m = MailMessage(id="2", subject="hello", from_="x@y")
    s.save_message(m)
    ids = s.get_message_ids()
    assert "2" in ids
