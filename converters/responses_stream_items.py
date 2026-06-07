"""Completed output item builders for Responses SSE conversion."""

from __future__ import annotations


def completed_message_item(item_id: str, text: str) -> dict:
    return {
        "type": "message",
        "id": item_id,
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text}],
    }


def completed_reasoning_item(item_id: str, text: str) -> dict:
    return {
        "type": "reasoning",
        "id": item_id,
        "status": "completed",
        "summary": [{"type": "summary_text", "text": text}],
        "encrypted_content": None,
    }


def completed_tool_item(entry: dict) -> dict:
    return {
        "type": "function_call",
        "id": entry["id"],
        "call_id": entry["call_id"],
        "name": entry["name"],
        "arguments": entry["arguments"] or "{}",
        "status": "completed",
    }


def incomplete_reason(finish_reason: str) -> str:
    if finish_reason == "length":
        return "max_output_tokens"
    if finish_reason == "content_filter":
        return "content_filter"
    return ""
