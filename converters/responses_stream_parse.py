"""Parsing helpers for shimmed chat SSE to Responses SSE conversion."""

from __future__ import annotations

import json


def parse_chat_sse_line(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if payload == "[DONE]":
        return {"__done__": True}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def reasoning_delta(delta: dict) -> str:
    for key in ("reasoning_content", "reasoning", "reasoning_text"):
        value = delta.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def tool_arguments_delta(arguments: object) -> str:
    if isinstance(arguments, str):
        return arguments
    if arguments is None:
        return ""
    return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
