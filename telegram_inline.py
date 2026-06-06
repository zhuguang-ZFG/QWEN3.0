"""Telegram inline query handler (TG-10.0-3)."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

import http_caller
import routing_engine
import telegram_bot

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

_INLINE_MAX_QUERY = 500
_INLINE_MAX_ANSWER = 3900
_RATE_WINDOW_SEC = 60.0
_RATE_MAX = 10
_seen: dict[str, list[float]] = {}


def inline_enabled() -> bool:
    return os.environ.get("TELEGRAM_INLINE_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def reset_inline_rate_limit_for_tests() -> None:
    _seen.clear()


def _rate_ok(user_key: str) -> bool:
    now = time.monotonic()
    bucket = _seen.setdefault(user_key, [])
    _seen[user_key] = [t for t in bucket if now - t < _RATE_WINDOW_SEC]
    if len(_seen[user_key]) >= _RATE_MAX:
        return False
    _seen[user_key].append(now)
    return True


def _extract_answer(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("answer") or "").strip()
    return str(getattr(result, "answer", result) or "").strip()


def route_inline_query(text: str) -> str:
    query = (text or "").strip()
    if not query:
        return "请输入问题，例如：斐波那契数列是什么"
    if len(query) > _INLINE_MAX_QUERY:
        query = query[:_INLINE_MAX_QUERY]
    result = routing_engine.route(
        query=query,
        messages=[{"role": "user", "content": query}],
        call_fn=http_caller.call_api,
    )
    answer = _extract_answer(result) or "(empty response)"
    if len(answer) > _INLINE_MAX_ANSWER:
        answer = answer[: _INLINE_MAX_ANSWER - 3] + "..."
    return answer


def build_inline_results(query: str, answer: str) -> list[dict[str, Any]]:
    q = (query or "").strip() or "LiMa"
    digest = hashlib.sha256(f"{q}\n{answer}".encode()).hexdigest()[:16]
    body = f"LiMa · {q}\n\n{answer}"
    if len(body) > 4096:
        body = body[:4093] + "..."
    title = q[:64] if q else "LiMa"
    description = answer.replace("\n", " ")[:120]
    return [
        {
            "type": "article",
            "id": digest,
            "title": title,
            "description": description,
            "input_message_content": {"message_text": body},
        }
    ]


def _hint_results() -> list[dict[str, Any]]:
    return [
        {
            "type": "article",
            "id": "lima-inline-hint",
            "title": "LiMa inline",
            "description": "输入问题，例如：查天气 / 斐波那契",
            "input_message_content": {
                "message_text": "LiMa inline：请在 @bot 后输入你的问题。",
            },
        }
    ]


async def handle_inline_query(inline_query: dict[str, Any]) -> bool:
    if not inline_enabled() or not telegram_bot.is_configured():
        return False

    query_id = str(inline_query.get("id") or "")
    if not query_id:
        return False

    from_user = inline_query.get("from") or {}
    user_id = from_user.get("id")
    if not telegram_bot.is_authorized(user_id):
        await telegram_bot.answer_inline_query(query_id, [], cache_time=5)
        return True

    raw_query = str(inline_query.get("query") or "")
    if not raw_query.strip():
        await telegram_bot.answer_inline_query(query_id, _hint_results(), cache_time=10)
        return True

    if not _rate_ok(str(user_id)):
        limited = build_inline_results(raw_query, "请求过于频繁，请稍后再试。")
        await telegram_bot.answer_inline_query(query_id, limited, cache_time=5)
        return True

    try:
        answer = route_inline_query(raw_query)
    except Exception as exc:
        logger.exception("inline query route failed")
        answer = "LiMa 暂时无法回答，请稍后在私聊中使用 /chat。"

    results = build_inline_results(raw_query, answer)
    await telegram_bot.answer_inline_query(query_id, results, cache_time=30)
    return True
