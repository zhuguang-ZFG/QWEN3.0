"""Append-only operator archive via Telegram chat history (TG-S3 v0.1, default off)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Awaitable, Callable

import telegram_bot

_log = logging.getLogger(__name__)

_DEFAULT_CHUNK = 3900


def archive_enabled() -> bool:
    return os.environ.get("LIMA_TG_ARCHIVE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def chunk_text(text: str, *, limit: int = _DEFAULT_CHUNK) -> list[str]:
    """Split long text on line boundaries for Telegram sendMessage."""
    body = (text or "").strip()
    if not body:
        return []
    if len(body) <= limit:
        return [body]

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in body.splitlines():
        line_len = len(line) + 1
        if current and size + line_len > limit:
            chunks.append("\n".join(current))
            current = [line]
            size = line_len
        else:
            current.append(line)
            size += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def format_archive_message(label: str, body: str) -> str:
    tag = (label or "artifact").strip()[:80]
    return f"[TG-ARCHIVE] {tag}\n{body.strip()}"


def _fire_and_forget(coro_fn: Callable[[], Awaitable[None]]) -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro_fn())
            return
    except RuntimeError:
        pass
    threading.Thread(target=asyncio.run, args=(coro_fn(),), daemon=True).start()


async def archive_text_async(
    label: str,
    body: str,
    *,
    chat_id: str = "",
    parse_mode: str = "",
) -> bool:
    if not archive_enabled() or not telegram_bot.is_configured():
        return False
    message = format_archive_message(label, body)
    parts = chunk_text(message)
    if not parts:
        return False
    ok = True
    for idx, part in enumerate(parts, start=1):
        prefix = f"({idx}/{len(parts)})\n" if len(parts) > 1 else ""
        sent = await telegram_bot.send_message(
            prefix + part,
            chat_id=chat_id,
            parse_mode=parse_mode,
        )
        ok = ok and sent
    return ok


def archive_text(
    label: str,
    body: str,
    *,
    chat_id: str = "",
    parse_mode: str = "",
) -> bool:
    if not archive_enabled() or not telegram_bot.is_configured():
        _log.debug("tg archive skipped (disabled or bot not configured)")
        return False

    async def _run() -> None:
        await archive_text_async(
            label,
            body,
            chat_id=chat_id,
            parse_mode=parse_mode,
        )

    _fire_and_forget(_run)
    return True


async def archive_file_async(
    file_path: str | Path,
    label: str,
    *,
    chat_id: str = "",
) -> bool:
    """Upload JSON/file to operator chat (TG-S3 v0.2 sendDocument)."""
    if not archive_enabled() or not telegram_bot.is_configured():
        return False
    path = Path(file_path)
    if not path.is_file():
        _log.warning("tg archive file missing: %s", path)
        return False
    caption = f"[TG-ARCHIVE] {(label or path.name).strip()[:80]}"
    return await telegram_bot.send_document(
        path,
        chat_id=chat_id,
        caption=caption,
        filename=path.name,
    )


def archive_file(
    file_path: str | Path,
    label: str,
    *,
    chat_id: str = "",
) -> bool:
    if not archive_enabled() or not telegram_bot.is_configured():
        _log.debug("tg archive file skipped (disabled or bot not configured)")
        return False

    async def _run() -> None:
        await archive_file_async(file_path, label, chat_id=chat_id)

    _fire_and_forget(_run)
    return True
