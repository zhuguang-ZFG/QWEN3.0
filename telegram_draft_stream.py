"""Telegram sendMessageDraft streaming for /chat (Bot API 9.3+, TG-10.0-1)."""

from __future__ import annotations

import logging
import os
import time

import telegram_bot

logger = logging.getLogger(__name__)

DEFAULT_THROTTLE_MS = 800.0
MAX_DRAFT_CHARS = 4096
MAX_FINAL_CHARS = 4000


def stream_chat_enabled() -> bool:
    return os.environ.get("TELEGRAM_STREAM_CHAT", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _throttle_ms() -> float:
    raw = os.environ.get("TELEGRAM_STREAM_THROTTLE_MS", "").strip()
    if not raw:
        return DEFAULT_THROTTLE_MS
    try:
        return max(200.0, float(raw))
    except ValueError:
        return DEFAULT_THROTTLE_MS


def _chat_id_param(chat_id: str) -> int | str:
    text = str(chat_id).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return text


class TelegramDraftStreamer:
    """Stream partial text via sendMessageDraft; persist with sendMessage."""

    def __init__(self, chat_id: str, draft_id: int = 1) -> None:
        self.chat_id = chat_id
        self.draft_id = draft_id
        self._throttle_sec = _throttle_ms() / 1000.0
        self._buffer = ""
        self._last_sent = ""
        self._last_at = 0.0
        self._stopped = False

    async def start(self) -> None:
        await self._send_draft("")

    async def push(self, text: str, *, force: bool = False) -> None:
        if self._stopped:
            return
        if len(text) > MAX_DRAFT_CHARS:
            self._buffer = text[:MAX_DRAFT_CHARS]
            self._stopped = True
        else:
            self._buffer = text
        if not force and self._buffer == self._last_sent:
            return
        now = time.monotonic()
        if (
            not force
            and self._last_sent
            and (now - self._last_at) < self._throttle_sec
        ):
            return
        await self._send_draft(self._buffer)

    async def finalize(self, text: str | None = None) -> bool:
        final = (text if text is not None else self._buffer).strip()
        if not final:
            final = "(empty response)"
        if len(final) > MAX_FINAL_CHARS:
            final = final[: MAX_FINAL_CHARS - 3] + "..."
        if not self._stopped:
            await self.push(final, force=True)
        return await telegram_bot.send_message(final, parse_mode="", chat_id=self.chat_id)

    async def _send_draft(self, text: str) -> None:
        if not telegram_bot.is_configured():
            self._stopped = True
            return
        result = await telegram_bot._api_call(
            "sendMessageDraft",
            {
                "chat_id": _chat_id_param(self.chat_id),
                "draft_id": self.draft_id,
                "text": text,
            },
        )
        if result is None or not result.get("ok"):
            self._stopped = True
            logger.warning("sendMessageDraft failed for chat_id=%s", self.chat_id)
            return
        self._last_sent = text
        self._last_at = time.monotonic()
