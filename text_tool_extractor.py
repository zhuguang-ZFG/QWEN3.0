"""text_tool_extractor.py — Extract tool calls from model text output.

Models like Kimi K2.6, Qwen, and other open-source models don't natively
support the OpenAI tool_calls protocol. Instead they output tool calls as
JSON code blocks in the content. This module detects and converts them.

Format detected:
  ```json
  {"name": "tool_name", "arguments": {...}}
  ```
  or
  {"name": "tool_name", "arguments": {...}}

Also supports multi-tool arrays:
  ```json
  [{"name": "t1", "arguments": {...}}, {"name": "t2", "arguments": {...}}]
  ```
"""

from __future__ import annotations

import json
import re
import uuid

# Backends known to output tool calls as text instead of protocol
TEXT_TOOL_BACKENDS = {
    "kimi", "kimi_thinking", "kimi_search",
    "cfai_qwen_coder", "cf_mistral",
}


def extract_tool_calls_from_text(content: str) -> tuple[str, list[dict] | None]:
    """Parse tool-call JSON from text content.

    Returns (cleaned_content, tool_calls_or_None).
    tool_calls is in OpenAI format: [{"id": ..., "type": "function", "function": {...}}]
    """
    if not content:
        return content, None

    tool_calls = []
    cleaned = content

    # Pattern 1: ```json ... ``` code blocks
    json_block_pattern = re.compile(
        r"```json\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE
    )
    for match in json_block_pattern.finditer(content):
        json_str = match.group(1).strip()
        parsed = _parse_tool_json(json_str)
        if parsed:
            tool_calls.extend(parsed)
            cleaned = cleaned.replace(match.group(0), "")

    # Pattern 2: Raw JSON objects on their own lines (no code fence)
    if not tool_calls:
        raw_json_pattern = re.compile(
            r'(?:^|\n)\s*(\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\s*\})',
            re.DOTALL,
        )
        for match in raw_json_pattern.finditer(content):
            json_str = match.group(1).strip()
            parsed = _parse_tool_json(json_str)
            if parsed:
                tool_calls.extend(parsed)
                cleaned = cleaned.replace(match.group(1), "")

    # Clean up extra whitespace from removed blocks
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        cleaned = ""

    return cleaned, (tool_calls if tool_calls else None)


def _parse_tool_json(json_str: str) -> list[dict] | None:
    """Parse a JSON string into OpenAI-format tool_calls. Returns None if invalid."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    # Normalize to list
    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return None

    tool_calls = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        arguments = item.get("arguments", {})
        if not name:
            continue
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        tool_calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            }
        )

    return tool_calls if tool_calls else None


def should_extract_tools(backend: str) -> bool:
    """Check if this backend is known to output tools as text."""
    return backend in TEXT_TOOL_BACKENDS
