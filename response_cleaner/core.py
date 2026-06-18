"""Core response cleaning entry points."""

import re

from response_cleaner.error_detection import _is_backend_error
from response_cleaner.identity import _looks_like_self_identity, apply_identity_cleaning
from response_cleaner.patterns import CLEAN_PATTERNS


def clean_response(text: str, backend_name: str = "") -> str:
    """清洗响应：隐藏底层模型/供应商信息，剥离思维链。"""
    del backend_name  # reserved for future backend-specific rules
    if not text or "[ERR]" in text[:15]:
        return ""
    if _is_backend_error(text):
        return ""
    # Strip <think>...</think> blocks (some backends expose reasoning)
    text = re.sub(r"<think>[\s\S]*?</think>\s*", "", text)
    # Strip unclosed <think> at start (partial thinking leak)
    if text.startswith("<think>"):
        text = ""
    if _looks_like_self_identity(text):
        for pattern, repl in CLEAN_PATTERNS:
            text = pattern.sub(repl, text)
        from identity_guard import filter_identity_leak

        prefer = "cn" if any("一" <= c <= "鿿" for c in text) else "en"
        text = filter_identity_leak(text, prefer_language=prefer)
    return text.strip()


def _clean_brand_only(text: str, backend_name: str = "") -> str:
    """Streaming helper: clean a chunk with identity-aware patterns."""
    del backend_name  # reserved for future backend-specific rules
    if not text:
        return ""
    if not _looks_like_self_identity(text):
        return text
    cleaned = apply_identity_cleaning(text)
    from identity_guard import filter_identity_leak

    return filter_identity_leak(cleaned)
