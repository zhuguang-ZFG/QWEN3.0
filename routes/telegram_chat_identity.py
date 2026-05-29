"""Telegram chat identity intercept and response sanitization."""

from __future__ import annotations

import identity_guard
from response_cleaner import clean_response


def maybe_identity_answer(query: str, *, channel_role: str = "default") -> str | None:
    """Return preset LiMa identity answer, or None for normal routing."""
    return identity_guard.detect_identity_question(query, channel_role=channel_role)


def sanitize_chat_answer(query: str, answer: str, *, backend: str = "telegram") -> str:
    """Strip backend model leaks before sending to Telegram."""
    if not answer:
        return answer
    cleaned = clean_response(answer, backend)
    prefer = "cn" if _is_chinese(query or answer) else "en"
    return identity_guard.filter_identity_leak(cleaned, prefer_language=prefer)


def _is_chinese(text: str) -> bool:
    cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cn_chars > len(text) * 0.1
