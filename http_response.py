"""Response parsing helpers for http_caller (CQ-014 slice 8)."""

from __future__ import annotations

import json


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
    message = data["choices"][0]["message"]
    return (
        message.get("content")
        or message.get("reasoning_content")
        or message.get("reasoning")
        or ""
    )


def _extract_usage(data: dict, fmt: str) -> tuple[int, int]:
    usage = data.get("usage", {})
    if fmt == "anthropic":
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _parse_sse_chunk(data_str: str, fmt: str) -> str:
    try:
        data = json.loads(data_str)
        if fmt == "openai":
            delta = data["choices"][0]["delta"]
            return (
                delta.get("content")
                or delta.get("reasoning_content")
                or ""
            )
        if data.get("type") == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return delta.get("text", "")
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return ""


def extract_sse_usage(data_str: str) -> dict | None:
    """Extract usage stats from an SSE chunk (OpenAI format). Returns None if no usage."""
    try:
        data = json.loads(data_str)
        usage = data.get("usage")
        if usage and isinstance(usage, dict) and usage.get("prompt_tokens"):
            return usage
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def extract_sse_reasoning(data_str: str, fmt: str) -> str:
    """Extract reasoning_content from an SSE chunk without including it in content."""
    try:
        data = json.loads(data_str)
        if fmt == "openai":
            delta = data.get("choices", [{}])[0].get("delta", {})
            return delta.get("reasoning_content") or ""
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return ""
