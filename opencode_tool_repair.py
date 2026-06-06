"""opencode_tool_repair.py — Tool name auto-repair and invalid tool routing.

复刻 OpenCode session/llm.ts experimental_repairToolCall() (L290-309)。
当模型返回大小写不匹配的工具名时，自动修正为正确的工具名。
若工具完全无法识别，则路由到 "invalid" 工具，返回错误信息让模型自行修正。

核心功能:
  1. repair_tool_call() — 修复单个工具调用名称
  2. repair_tool_calls_in_messages() — 批量修复消息中的工具调用
  3. build_invalid_tool() — 构建 "invalid" 工具定义
"""

from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)

# The "invalid" tool is used as a fallback when a tool call cannot be repaired.
# The model receives an error message as the tool result and can self-correct.
INVALID_TOOL_NAME = "invalid"

_INVALID_TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": INVALID_TOOL_NAME,
        "description": (
            "This tool is a fallback for when a tool call could not be repaired. "
            "The tool name was not recognized. Please check available tools and retry."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "description": "The original tool name that failed.",
                },
                "error": {
                    "type": "string",
                    "description": "The error message from the failed call.",
                },
            },
            "required": ["tool", "error"],
        },
    },
}


def repair_tool_name(
    tool_name: str,
    available_tools: dict[str, Any] | list[str],
) -> str | None:
    """Try to repair a tool name by case-insensitive matching.

    Ported from llm.ts experimental_repairToolCall() (L290-301).

    Args:
        tool_name: The tool name from the model's tool call.
        available_tools: Dict mapping tool names to definitions, or list of names.

    Returns:
        Repaired tool name if found, or None if no match.
    """
    if not tool_name:
        return None

    # Build lowercase lookup
    if isinstance(available_tools, dict):
        lower_map = {k.lower(): k for k in available_tools}
    else:
        lower_map = {name.lower(): name for name in available_tools}

    lower = tool_name.lower()

    # Exact match (no repair needed)
    if tool_name in lower_map.values():
        return tool_name

    # Case-insensitive match → return correct case
    if lower in lower_map:
        repaired = lower_map[lower]
        _log.info("Repaired tool call: %s → %s", tool_name, repaired)
        return repaired

    return None


def build_invalid_tool_result(
    tool_name: str,
    error_message: str = "Tool not found",
) -> dict[str, str]:
    """Build an error result for an unrepairable tool call.

    Ported from llm.ts (L302-309).
    The model receives this as the tool result, allowing it to self-correct.

    Args:
        tool_name: The original (failed) tool name.
        error_message: Error description.

    Returns:
        Dict with 'tool' and 'error' keys, JSON-serializable as the tool input.
    """
    return {
        "tool": tool_name,
        "error": error_message,
    }


def build_invalid_tool_input_json(tool_name: str, error_message: str) -> str:
    """Build the JSON input string for the 'invalid' tool.

    Returns JSON string like {"tool": "xxx", "error": "yyy"}.
    """
    return json.dumps(build_invalid_tool_result(tool_name, error_message))


def get_invalid_tool_definition() -> dict[str, Any]:
    """Return the 'invalid' tool definition to add to the tools list.

    This tool should be included when tool repair is active,
    so the model can route unrepairable calls to it.
    """
    return dict(_INVALID_TOOL_DEFINITION)


def repair_tool_calls_in_body(
    body: dict[str, Any],
    available_tool_names: list[str] | None = None,
) -> dict[str, Any]:
    """Repair tool calls in a request body's messages.

    Scans all messages for tool_calls (OpenAI format) and attempts
    case-insensitive name repair. Unrepairable calls are redirected
    to the "invalid" tool.

    Args:
        body: The request body dict (will not be mutated).
        available_tool_names: List of valid tool names. If None, extracted
                              from body["tools"].

    Returns:
        New body dict with repaired tool calls.
    """
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        return body

    # Build available tool names from body if not provided
    if available_tool_names is None:
        tools = body.get("tools", [])
        available_tool_names = []
        for t in tools:
            fn = t.get("function", {})
            name = fn.get("name", "")
            if name and name != INVALID_TOOL_NAME:
                available_tool_names.append(name)

    if not available_tool_names:
        return body

    lower_map = {n.lower(): n for n in available_tool_names}
    changed = False
    new_messages: list[dict] = []

    for msg in messages:
        tool_calls = msg.get("tool_calls")
        if not tool_calls or not isinstance(tool_calls, list):
            new_messages.append(msg)
            continue

        fixed_calls = []
        msg_changed = False
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")

            if name in lower_map.values():
                # Exact match — keep as-is
                fixed_calls.append(tc)
            elif name.lower() in lower_map:
                # Case-insensitive match → repair
                repaired = lower_map[name.lower()]
                fixed_calls.append({
                    **tc,
                    "function": {**fn, "name": repaired},
                })
                msg_changed = True
                _log.info("Repaired tool call in body: %s → %s", name, repaired)
            else:
                # No match → route to "invalid"
                error_msg = f"Tool '{name}' not found. Available: {', '.join(available_tool_names[:10])}"
                fixed_calls.append({
                    **tc,
                    "function": {
                        "name": INVALID_TOOL_NAME,
                        "arguments": build_invalid_tool_input_json(name, error_msg),
                    },
                })
                msg_changed = True
                _log.warning("Routed unknown tool '%s' to invalid", name)

        if msg_changed:
            new_messages.append({**msg, "tool_calls": fixed_calls})
            changed = True
        else:
            new_messages.append(msg)

    if not changed:
        return body

    result = {**body, "messages": new_messages}

    # Ensure "invalid" tool is in the tools list
    tools = result.get("tools", [])
    has_invalid = any(
        t.get("function", {}).get("name") == INVALID_TOOL_NAME for t in tools
    )
    if not has_invalid:
        result["tools"] = tools + [get_invalid_tool_definition()]

    return result


def should_inject_invalid_tool(tools: list[dict]) -> bool:
    """Check if tools list needs the 'invalid' tool injected.

    The 'invalid' tool should be present whenever tools are defined,
    as a fallback for unrepairable tool calls.
    """
    if not tools:
        return False
    return not any(
        t.get("function", {}).get("name") == INVALID_TOOL_NAME for t in tools
    )
