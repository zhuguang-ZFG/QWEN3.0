"""Stream /chat replies to Telegram via sendMessageDraft (TG-10.0-1)."""

from __future__ import annotations

import logging

from routes.stream_handlers import speculative_stream_chunks
from telegram_draft_stream import TelegramDraftStreamer

logger = logging.getLogger(__name__)


async def stream_chat_to_telegram(
    chat_id: str,
    query: str,
    messages: list[dict],
    *,
    max_tokens: int = 4096,
) -> str:
    streamer = TelegramDraftStreamer(chat_id)
    await streamer.start()

    accumulated = ""
    async for _backend, chunk in speculative_stream_chunks(
        query, messages, max_tokens, "telegram"
    ):
        accumulated += chunk
        await streamer.push(accumulated)

    if not accumulated.strip():
        accumulated = "(empty response)"

    ok = await streamer.finalize(accumulated)
    if not ok:
        logger.warning("Telegram finalize sendMessage failed chat_id=%s", chat_id)
    return accumulated
