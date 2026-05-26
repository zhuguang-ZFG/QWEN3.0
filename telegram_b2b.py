"""Telegram Bot-to-Bot ingress from LiMa Code (Bot API 10.0, TG-10.0-2)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import telegram_notify

logger = logging.getLogger(__name__)

PREFIX = "LIMA_B2B\n"
ACK_PREFIX = "LIMA_B2B_ACK\n"
_RATE_WINDOW_SEC = 60.0
_RATE_MAX = 30
_seen: dict[str, list[float]] = {}


def b2b_enabled() -> bool:
    return os.environ.get("TELEGRAM_B2B_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def allowed_code_bot_usernames() -> set[str]:
    raw = os.environ.get("TELEGRAM_CODE_BOT_USERNAMES", "").strip()
    return {part.strip().lower().lstrip("@") for part in raw.split(",") if part.strip()}


def parse_b2b_payload(text: str) -> dict[str, Any] | None:
    if not text.startswith(PREFIX):
        return None
    try:
        payload = json.loads(text[len(PREFIX) :].strip())
    except json.JSONDecodeError:
        logger.warning("b2b json decode failed")
        return None
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return None
    return payload


def format_b2b_ack(ok: bool, *, event_type: str = "", detail: str = "") -> str:
    body = {"ok": ok, "type": event_type}
    if detail:
        body["detail"] = detail[:200]
    return ACK_PREFIX + json.dumps(body, ensure_ascii=False)


def _rate_ok(username: str) -> bool:
    now = time.monotonic()
    bucket = _seen.setdefault(username, [])
    _seen[username] = [t for t in bucket if now - t < _RATE_WINDOW_SEC]
    if len(_seen[username]) >= _RATE_MAX:
        return False
    _seen[username].append(now)
    return True


def reset_b2b_rate_limit_for_tests() -> None:
    _seen.clear()


def _dispatch_event(payload: dict[str, Any]) -> tuple[bool, str]:
    event_type = str(payload.get("type") or "").strip()
    task_id = str(payload.get("task_id") or "").strip()
    summary = str(payload.get("summary") or "").strip() or "(no summary)"
    files_raw = payload.get("changed_files")
    changed_files = (
        [str(f) for f in files_raw[:20]]
        if isinstance(files_raw, list)
        else []
    )

    if event_type == "task_needs_review":
        if not task_id:
            return False, "missing task_id"
        telegram_notify.notify_task_ready(task_id, summary, changed_files)
        return True, ""

    if event_type in {
        "task_started",
        "task_finished",
        "task_failed",
        "work_stopped",
        "quarantine_requested",
    }:
        telegram_notify.notify_code_lifecycle(
            event_type, task_id, summary, changed_files
        )
        return True, ""

    return False, f"unsupported type: {event_type}"


async def handle_inbound_b2b(message: dict[str, Any]) -> tuple[bool, str, str]:
    """Return (handled, reply_chat_id, ack_text)."""
    if not b2b_enabled():
        return False, "", ""

    from_user = message.get("from") or {}
    if not from_user.get("is_bot"):
        return False, "", ""

    username = str(from_user.get("username") or "").lower().lstrip("@")
    allowed = allowed_code_bot_usernames()
    if not allowed or username not in allowed:
        logger.warning("b2b rejected sender username=%s", username or "?")
        return False, "", ""

    if not _rate_ok(username):
        chat_id = str(message.get("chat", {}).get("id", ""))
        return True, chat_id, format_b2b_ack(False, detail="rate_limited")

    text = message.get("text") or ""
    payload = parse_b2b_payload(text)
    if payload is None:
        return False, "", ""

    ok, detail = _dispatch_event(payload)
    chat_id = str(message.get("chat", {}).get("id", ""))
    ack = format_b2b_ack(ok, event_type=str(payload.get("type") or ""), detail=detail)
    return True, chat_id, ack
