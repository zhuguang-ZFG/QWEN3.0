"""Telegram operator tools — codesearch status and probe."""

from __future__ import annotations

import asyncio
import logging

import telegram_bot
from routes.telegram_commands import _operator_error
from search_gateway.codesearch_status import (
    build_codesearch_status,
    format_search_result,
    probe_search,
)

_log = logging.getLogger(__name__)
_PLAIN = ""


async def cmd_codesearch(chat_id: str, args: str) -> None:
    query = (args or "").strip()
    if not query:
        await telegram_bot.send_message(
            build_codesearch_status(),
            chat_id=chat_id,
            parse_mode=_PLAIN,
        )
        return

    await telegram_bot.send_message(
        f"Codesearch 查询中: {query[:80]}…",
        chat_id=chat_id,
        parse_mode=_PLAIN,
    )

    try:
        payload = await asyncio.to_thread(probe_search, query)
        text = format_search_result(payload)
        await telegram_bot.send_message(text, chat_id=chat_id, parse_mode=_PLAIN)
    except Exception:
        _log.exception("cmd_codesearch search failed")
        await telegram_bot.send_message(_operator_error("codesearch"), chat_id=chat_id)
