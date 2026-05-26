"""Optional translation for Telegram push notifications (TG-GH-7)."""

from __future__ import annotations

import os
import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def push_translate_enabled() -> bool:
    return os.environ.get("TELEGRAM_PUSH_TRANSLATE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def push_translate_target() -> str:
    return os.environ.get("TELEGRAM_PUSH_TRANSLATE_LANG", "zh-CN").strip() or "zh-CN"


def mostly_chinese(text: str) -> bool:
    sample = (text or "")[:800]
    if not sample.strip():
        return True
    cjk = len(_CJK_RE.findall(sample))
    letters = sum(1 for ch in sample if ch.isalpha())
    if letters == 0:
        return cjk > 0
    return cjk / max(letters, 1) >= 0.25


def translate_push_text(text: str, *, target: str | None = None) -> str:
    """Translate outbound push text when enabled; skip if already Chinese."""
    body = (text or "").strip()
    if not body or not push_translate_enabled() or mostly_chinese(body):
        return text

    from channel_gateway.public_apis import translate_text_only

    lang = target or push_translate_target()
    chunk = body[:500]
    translated = translate_text_only(chunk, target=lang)
    if not translated:
        return text

    if len(body) <= 420:
        return f"{body}\n\n【译】{translated}"
    return f"{body[:420]}…\n\n【译】{translated}"
