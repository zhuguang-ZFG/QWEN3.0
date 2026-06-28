"""Response parsing helpers for http_caller (CQ-014 slice 8)."""

from __future__ import annotations

import json
import logging

_log = logging.getLogger(__name__)


def _extract_answer(data: dict, fmt: str) -> str:
    if fmt == "anthropic":
        text_content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content = block.get("text", "")
                break
        if text_content:
            return text_content
        for block in data.get("content", []):
            if block.get("type") == "thinking":
                return block.get("thinking", "")
        return ""
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    return message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""


def _extract_usage(data: dict, fmt: str) -> tuple[int, int]:
    usage = data.get("usage", {})
    if fmt == "anthropic":
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _parse_sse_chunk(data_str: str, fmt: str) -> str:
    try:
        data = json.loads(data_str)
        if fmt == "openai":
            choices = data.get("choices")
            if not choices or not isinstance(choices, list):
                return ""
            delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
            return delta.get("content") or delta.get("reasoning_content") or ""
        if data.get("type") == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return delta.get("text", "")
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        _log.warning("sse chunk parse failed: %s", exc)
    return ""
