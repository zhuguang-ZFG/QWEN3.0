"""Content helpers for the OpenAI Responses API shim."""

from __future__ import annotations

import json
from typing import Any

_MAX_IMAGE_MARKER = 180


def content_to_text(content: Any) -> str:
    """Convert Responses message content into chat-compatible text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [text_from_part(p) for p in content if isinstance(p, dict)]
        return "\n".join(p for p in parts if p)
    return str(content)


def text_from_part(part: dict) -> str:
    """Return the user-visible text represented by a Responses content part."""
    ptype = part.get("type", "")
    if ptype in ("input_text", "output_text", "text", "summary_text"):
        return str(part.get("text", "") or "")
    if ptype == "input_image":
        return _image_marker(part.get("image_url"))
    return ""


def tool_output_continuation_text(item: dict) -> str:
    """Build a non-empty continuation prompt for standalone tool outputs."""
    call_id = str(item.get("call_id") or item.get("id") or "unknown")
    output = tool_output_to_text(item.get("output", ""))
    return (
        f"Tool output for call {call_id}:\n"
        f"{output}\n\n"
        "Continue from this tool result and answer the user's request."
    )


def tool_output_to_text(output: Any) -> str:
    """Render Responses function_call_output values as model-readable text."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts = []
        for item in output:
            if isinstance(item, dict):
                text = text_from_part(item)
                if text:
                    parts.append(text)
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(output, dict):
        return json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    return str(output or "")


def is_replay_metadata_item(item: dict) -> bool:
    """Return true for opaque Responses replay items that chat backends cannot use."""
    return item.get("type") == "item_reference"


def _image_marker(image_url: Any) -> str:
    if not isinstance(image_url, str) or not image_url:
        return "[image]"
    if len(image_url) <= _MAX_IMAGE_MARKER:
        return f"[image: {image_url}]"
    return f"[image: {image_url[:_MAX_IMAGE_MARKER]}...]"
