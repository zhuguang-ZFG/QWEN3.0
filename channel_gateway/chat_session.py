"""Lightweight multi-turn chat context for WeChat channel (G3)."""

from __future__ import annotations

import os

from channel_gateway.store import ChannelStore


def session_enabled() -> bool:
    return os.environ.get("LIMA_CHANNEL_SESSION", "1") == "1"


def max_turns() -> int:
    try:
        return max(1, min(20, int(os.environ.get("LIMA_CHANNEL_SESSION_TURNS", "6"))))
    except ValueError:
        return 6


class ChannelChatSession:
    """Per-user rolling chat history stored in ChannelStore."""

    def __init__(self, store: ChannelStore):
        self._store = store

    def get_messages(self, channel_user_id_raw: str) -> list[dict[str, str]]:
        if not session_enabled():
            return []
        user_hash = self._store._hash_id(channel_user_id_raw)
        return self._store.get_chat_history(user_hash, max_messages=max_turns() * 2)

    def record_turn(
        self, channel_user_id_raw: str, role: str, content: str
    ) -> None:
        if not session_enabled() or not content.strip():
            return
        user_hash = self._store._hash_id(channel_user_id_raw)
        self._store.append_chat_turn(user_hash, role, content.strip()[:2000])
        self._store.trim_chat_history(user_hash, max_messages=max_turns() * 2)

    def clear(self, channel_user_id_raw: str) -> None:
        user_hash = self._store._hash_id(channel_user_id_raw)
        self._store.clear_chat_history(user_hash)
