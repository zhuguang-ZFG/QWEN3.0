"""Sanitization helpers for outcome records."""

from __future__ import annotations

import json
import re
from typing import Any


def _clean_text(text: str, max_len: int = 500) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", cleaned)
    for pattern in ("sk-", "gho_", "ghp_", "github_pat_"):
        cleaned = re.sub(rf"(^|\s)({re.escape(pattern)}\S+)", r"\1[REDACTED]", cleaned)
    return cleaned[:max_len]


def _clean_value(value: Any, *, max_items: int = 50) -> Any:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, dict):
        return {
            _clean_text(str(k), 80): _clean_value(v, max_items=max_items) for k, v in list(value.items())[:max_items]
        }
    if isinstance(value, (list, tuple)):
        return [_clean_value(v, max_items=max_items) for v in list(value)[:max_items]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clean_text(str(value))


def _clean_list(values: list[str] | None, *, max_items: int = 10) -> list[Any]:
    return [_clean_value(v) for v in list(values or [])[:max_items]]


def _json_loads_safe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []
