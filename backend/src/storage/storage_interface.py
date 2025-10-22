from __future__ import annotations

from typing import List, Optional

from ..models.message import MailMessage


class StorageBackend:
    """Interface for storage backends."""

    def init_db(self) -> None:
        raise NotImplementedError()

    def save_message(self, msg: MailMessage) -> None:
        raise NotImplementedError()

    def get_message_ids(self) -> List[str]:
        raise NotImplementedError()

    def list_messages(self, limit: int = 100) -> List[MailMessage]:
        raise NotImplementedError()

    def get_history_id(self) -> Optional[str]:
        raise NotImplementedError()

    def set_history_id(self, history_id: str) -> None:
        raise NotImplementedError()
