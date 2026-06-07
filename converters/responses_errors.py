"""Error mapping helpers for OpenAI Responses API streams."""

from __future__ import annotations

from typing import Any


def chat_error_from_chunk(chunk: dict[str, Any]) -> dict[str, str | None] | None:
    raw = chunk.get("error")
    if not isinstance(raw, dict):
        return None
    message = raw.get("message") or raw.get("error") or "Upstream stream error"
    code = raw.get("code") or raw.get("type")
    param = raw.get("param")
    return {
        "message": str(message),
        "code": str(code) if code is not None else None,
        "param": str(param) if param is not None else None,
    }


def failed_response_payload(
    *,
    response_id: str,
    created_at: int,
    model: str,
    usage: dict[str, Any],
    error: dict[str, str | None],
) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "status": "failed",
        "created_at": created_at,
        "model": model,
        "output": [],
        "usage": usage,
        "error": error,
        "incomplete_details": None,
    }
