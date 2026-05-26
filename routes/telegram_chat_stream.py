"""Stream /chat replies to Telegram via sendMessageDraft (TG-10.0-1)."""

from __future__ import annotations

import asyncio
import logging

import http_caller
import routing_engine
import telegram_bot
from routes.stream_handlers import speculative_stream_chunks
from telegram_draft_stream import TelegramDraftStreamer, stream_chat_enabled

logger = logging.getLogger(__name__)

_EMPTY_FALLBACK = "系统暂时无法回答，请稍后重试。"


def _route_chat_sync(query: str, messages: list[dict]) -> str:
    msgs = messages if messages else [{"role": "user", "content": query}]
    result = routing_engine.route(
        query=query,
        messages=msgs,
        call_fn=http_caller.call_api,
        ide_source="telegram",
    )
    if isinstance(result, dict):
        answer = str(result.get("answer") or "").strip()
        if answer and not answer.startswith("[ERR]"):
            return answer
    try:
        from server_bootstrap import last_resort_call

        fallback = last_resort_call(msgs)
        if fallback and fallback.strip():
            return fallback.strip()
    except Exception as exc:
        logger.warning("telegram last_resort failed: %s", type(exc).__name__)
    return ""


async def stream_chat_to_telegram(
    chat_id: str,
    query: str,
    messages: list[dict],
    *,
    max_tokens: int = 4096,
) -> str:
    if not stream_chat_enabled():
        text = await asyncio.to_thread(_route_chat_sync, query, messages)
        if text:
            await telegram_bot.send_message(text, chat_id=chat_id, parse_mode="")
        return text or _EMPTY_FALLBACK

    streamer = TelegramDraftStreamer(chat_id)
    await streamer.start()

    accumulated = ""
    streamed_any = False
    async for _backend, chunk in speculative_stream_chunks(
        query, messages, max_tokens, "telegram"
    ):
        streamed_any = True
        accumulated += chunk
        await streamer.push(accumulated)

    if not accumulated.strip():
        accumulated = await asyncio.to_thread(_route_chat_sync, query, messages)
        if accumulated and not streamed_any:
            await streamer.push(accumulated, force=True)

    if not accumulated.strip():
        accumulated = _EMPTY_FALLBACK

    if streamer._stopped:
        ok = await telegram_bot.send_message(
            accumulated, chat_id=chat_id, parse_mode=""
        )
        if not ok:
            logger.warning("Telegram plain send failed chat_id=%s", chat_id)
        return accumulated

    ok = await streamer.finalize(accumulated)
    if not ok:
        logger.warning("Telegram finalize failed; retry plain send chat_id=%s", chat_id)
        await telegram_bot.send_message(accumulated, chat_id=chat_id, parse_mode="")
    return accumulated
