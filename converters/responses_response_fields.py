"""Response object metadata helpers for the Responses API shim."""

from __future__ import annotations

from typing import Any

_RESPONSE_FIELD_KEYS = (
    "instructions",
    "store",
    "prompt_cache_key",
    "prompt_cache_retention",
    "include",
    "reasoning",
    "text",
    "previous_response_id",
    "max_output_tokens",
    "max_tool_calls",
    "parallel_tool_calls",
    "temperature",
    "top_p",
    "tool_choice",
    "tools",
    "metadata",
    "user",
    "truncation",
    "service_tier",
    "safety_identifier",
    "top_logprobs",
    "background",
)


def response_fields_from_request(body: dict | None) -> dict[str, Any]:
    """Extract request fields that OpenAI Responses echoes in response objects."""
    if not isinstance(body, dict):
        return {}
    return {key: body[key] for key in _RESPONSE_FIELD_KEYS if key in body}


def with_response_fields(
    response: dict[str, Any],
    response_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge request-derived fields without overriding runtime response fields."""
    if not response_fields:
        return response
    merged = dict(response_fields)
    merged.update(response)
    return merged
