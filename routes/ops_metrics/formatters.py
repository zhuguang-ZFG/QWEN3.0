"""Ops metrics formatters — data transformation and redaction utilities."""

from __future__ import annotations

from typing import Any


def redacted(value: str, max_len: int = 40) -> str:
    """Redact sensitive string to max_len characters."""
    if not value:
        return ""
    return value[:max_len]


def backend_call_count(value: Any) -> int:
    """Extract call count from backend stats value."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, dict):
        count = value.get("count", 0)
        return int(count) if isinstance(count, int | float) else 0
    return 0


def backend_call_detail(value: Any) -> dict[str, Any]:
    """Extract detailed call stats (count, success, total_ms)."""
    if isinstance(value, dict):
        return {
            "count": backend_call_count(value),
            "success": int(value.get("success", 0)) if isinstance(value.get("success", 0), int | float) else 0,
            "total_ms": int(value.get("total_ms", 0)) if isinstance(value.get("total_ms", 0), int | float) else 0,
        }
    return {"count": backend_call_count(value), "success": 0, "total_ms": 0}


def top_backend_counts(backend_calls: dict[str, Any], limit: int = 10) -> dict[str, int]:
    """Return top N backends by call count."""
    ranked = sorted(
        ((name, backend_call_count(value)) for name, value in backend_calls.items()),
        key=lambda item: -item[1],
    )
    return dict(ranked[:limit])


def top_backend_details(backend_calls: dict[str, Any], limit: int = 10) -> dict[str, dict[str, Any]]:
    """Return top N backends with detailed stats."""
    ranked_names = list(top_backend_counts(backend_calls, limit=limit).keys())
    return {name: backend_call_detail(backend_calls[name]) for name in ranked_names}
