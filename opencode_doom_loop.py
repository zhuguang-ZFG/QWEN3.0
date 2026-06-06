"""opencode_doom_loop.py — Doom loop detection for repeated tool calls.

复刻 OpenCode session/processor.ts doom loop detection (L427-451)。
检测模型是否连续多次以相同参数调用同一工具（死循环）。
当检测到死循环时，返回警告信息以便客户端或后端介入。

核心功能:
  1. detect_doom_loop() — 检测消息中的重复工具调用
  2. build_doom_loop_warning() — 构建警告消息
"""

from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)

# Default threshold: 3 consecutive identical tool calls
DOOM_LOOP_THRESHOLD = 3


def _extract_tool_call_key(tc: dict) -> str | None:
    """Extract a canonical key from a tool call for comparison.

    Returns a string combining tool name and sorted arguments,
    or None if the tool call is malformed.
    """
    fn = tc.get("function", {})
    name = fn.get("name", "")
    if not name:
        return None

    # Normalize arguments for comparison
    args_raw = fn.get("arguments", "")
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw) if args_raw else {}
        except (json.JSONDecodeError, TypeError):
            args = {"_raw": args_raw}
    elif isinstance(args_raw, dict):
        args = args_raw
    else:
        args = {"_raw": str(args_raw)}

    # Sort keys for deterministic comparison
    canonical_args = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return f"{name}:{canonical_args}"


def detect_doom_loop(
    messages: list[dict],
    threshold: int = DOOM_LOOP_THRESHOLD,
) -> dict[str, Any] | None:
    """Detect if the last N assistant messages contain identical tool calls.

    Scans messages from the end, looking for consecutive assistant messages
    with the same tool call (same name + same arguments).

    Args:
        messages: Message list from the conversation.
        threshold: Number of consecutive identical calls to trigger detection.
                   Default is 3 (matching OpenCode processor.ts).

    Returns:
        Doom loop info dict if detected, None otherwise.
        Dict contains: {"tool_name": str, "count": int, "arguments": str}
    """
    if not messages or threshold < 2:
        return None

    # Collect recent assistant tool calls from the end
    recent_keys: list[str | None] = []
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            # Skip tool results (they're between assistant calls)
            if msg.get("role") == "tool":
                continue
            # User message breaks the chain
            break

        tool_calls = msg.get("tool_calls")
        if not tool_calls or not isinstance(tool_calls, list):
            break

        # Only check the first tool call per message (primary action)
        key = _extract_tool_call_key(tool_calls[0])
        if key is None:
            break
        recent_keys.append(key)

        if len(recent_keys) >= threshold:
            break

    if len(recent_keys) < threshold:
        return None

    # Check if all recent keys are identical
    first_key = recent_keys[0]
    if not all(k == first_key for k in recent_keys):
        return None

    # Doom loop detected — extract details
    _log.warning("Doom loop detected: %d identical calls to %s", len(recent_keys), first_key)

    # Parse the key back into name + arguments
    parts = first_key.split(":", 1)
    tool_name = parts[0]
    arguments = parts[1] if len(parts) > 1 else "{}"

    return {
        "tool_name": tool_name,
        "count": len(recent_keys),
        "arguments": arguments,
    }


def build_doom_loop_warning(info: dict[str, Any]) -> str:
    """Build a human-readable warning message for a doom loop.

    Args:
        info: Doom loop info dict from detect_doom_loop().

    Returns:
        Warning message string.
    """
    tool_name = info.get("tool_name", "unknown")
    count = info.get("count", 0)
    return (
        f"WARNING: The model has called '{tool_name}' {count} times "
        f"with identical arguments. This may indicate a loop. "
        f"Consider intervening or selecting a different approach."
    )


def inject_doom_loop_break(
    messages: list[dict],
    info: dict[str, Any],
) -> list[dict]:
    """Inject a system/user message to break a doom loop.

    Adds a user message telling the model to try a different approach.

    Args:
        messages: Current message list.
        info: Doom loop info from detect_doom_loop().

    Returns:
        New message list with break message appended.
    """
    warning = build_doom_loop_warning(info)
    break_msg = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    f"SYSTEM INTERVENTION: You have called '{info.get('tool_name', 'unknown')}' "
                    f"multiple times with the same arguments and it is not producing the "
                    f"desired result. Please try a DIFFERENT approach or tool. "
                    f"Do NOT call the same tool with the same arguments again."
                ),
            }
        ],
    }
    return [*messages, break_msg]
