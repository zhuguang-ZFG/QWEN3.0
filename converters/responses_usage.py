"""Usage mapping helpers for OpenAI Responses API payloads."""

from __future__ import annotations

from typing import Any


def chat_usage_to_responses_usage(usage_raw: dict[str, Any] | None) -> dict[str, Any]:
    """Map chat-completions usage fields to Responses API usage fields."""
    usage_raw = usage_raw or {}
    usage: dict[str, Any] = {
        "input_tokens": usage_raw.get("prompt_tokens", usage_raw.get("input_tokens", 0)),
        "output_tokens": usage_raw.get("completion_tokens", usage_raw.get("output_tokens", 0)),
        "total_tokens": usage_raw.get("total_tokens", 0),
    }

    cached_tokens = _nested_number(
        usage_raw,
        ("prompt_tokens_details", "cached_tokens"),
        ("input_tokens_details", "cached_tokens"),
    )
    if cached_tokens is not None:
        usage["input_tokens_details"] = {"cached_tokens": cached_tokens}

    reasoning_tokens = _nested_number(
        usage_raw,
        ("completion_tokens_details", "reasoning_tokens"),
        ("output_tokens_details", "reasoning_tokens"),
    )
    if reasoning_tokens is not None:
        usage["output_tokens_details"] = {"reasoning_tokens": reasoning_tokens}

    return usage


def _nested_number(data: dict[str, Any], *paths: tuple[str, str]) -> int | float | None:
    for parent, child in paths:
        node = data.get(parent)
        if isinstance(node, dict) and isinstance(node.get(child), int | float):
            return node[child]
    return None
