"""opencode_tool_splitter.py — 并行工具调用拆分为顺序调用（弱后端增强）。

OpenCode 支持 LLM 一次返回多个 tool_calls（如同时 read + grep）。
弱后端在并行工具调用时经常出现：JSON arguments 格式错误、tool_call_id 遗漏、
参数混淆、幻觉工具名。本模块在 SSE 流中检测并拆分并行工具调用。

核心功能:
  1. detect_parallel_tool_calls() — 检测 chunk 中的并行 tool_calls
  2. split_parallel_tool_calls() — 拆分为顺序调用列表
  3. validate_tool_call_args() — 校验 JSON arguments
  4. normalize_tool_call() / normalize_tool_calls_in_chunk() — 规范化 tool_calls

Extracted to opencode_tool_patterns.py:
  - repair_tool_call_json(), build_sequential_tool_prompt()
  - inject_tool_ordering_hint(), should_inject_sequential_hint()

源码参考:
  - opencode-source/packages/opencode/src/tool/registry.ts (builtin tools)
  - opencode-source/packages/opencode/src/tool/tool.ts (InvalidArgumentsError)
  - opencode-source/packages/llm/src/protocols/openai-chat.ts (tool_calls struct)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from opencode_tool_patterns import (
    _TOOL_ORDER_PRIORITY,
    repair_tool_call_json,
)

_log = logging.getLogger(__name__)

# Re-export for external consumers that imported from this module
from opencode_tool_patterns import (
    build_sequential_tool_prompt,
    inject_tool_ordering_hint,
    needs_tool_split,
    should_inject_sequential_hint,
)


def detect_parallel_tool_calls(chunk: dict) -> list[dict]:
    """检测 SSE chunk 中是否包含多个并行 tool_calls。

    Args:
        chunk: SSE chunk dict.

    Returns:
        提取的 tool_calls 列表。
    """
    choices = chunk.get("choices") or []
    all_calls: list[dict] = []

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        tool_calls = delta.get("tool_calls") or []
        for tc in tool_calls:
            if isinstance(tc, dict):
                all_calls.append(tc)

    return all_calls


def is_parallel_tool_call_chunk(chunk: dict) -> bool:
    """判断 chunk 是否包含并行工具调用（多个不同的 tool_call index）。"""
    calls = detect_parallel_tool_calls(chunk)
    if len(calls) <= 1:
        return False
    # Check if there are multiple distinct indices
    indices = {tc.get("index") for tc in calls if isinstance(tc.get("index"), int)}
    return len(indices) > 1


def split_parallel_tool_calls(
    chunk: dict,
    max_per_response: int = 1,
) -> list[dict]:
    """将包含多个并行 tool_calls 的 chunk 拆分为顺序调用。

    每个拆分后的 chunk 只包含一个 tool_call。

    Args:
        chunk: 原始 SSE chunk（可能包含多个 tool_calls）。
        max_per_response: 每个响应最多允许多少 tool_calls（默认 1）。

    Returns:
        拆分后的 chunk 列表。
    """
    calls = detect_parallel_tool_calls(chunk)
    if len(calls) <= max_per_response:
        return [chunk]

    # Group tool_calls by index
    by_index: dict[int, list[dict]] = {}
    for tc in calls:
        idx = tc.get("index", 0)
        by_index.setdefault(idx, []).append(tc)

    # Sort by tool order priority
    sorted_indices = sorted(by_index.keys(), key=lambda i: _get_tool_priority(calls, i))

    result = []
    for idx in sorted_indices:
        new_choices = []
        for choice in chunk.get("choices", []):
            if not isinstance(choice, dict):
                new_choices.append(choice)
                continue
            delta = choice.get("delta", {})
            original_calls = delta.get("tool_calls", [])
            # Keep only this index's calls
            filtered_calls = [tc for tc in original_calls if tc.get("index") == idx]
            if filtered_calls:
                new_choices.append({
                    **choice,
                    "delta": {**delta, "tool_calls": filtered_calls},
                })
        if new_choices:
            result.append({**chunk, "choices": new_choices})

    return result if result else [chunk]


def _get_tool_priority(calls: list[dict], index: int) -> int:
    """Get priority for a tool call index based on tool name."""
    for tc in calls:
        if tc.get("index") == index:
            fn = tc.get("function", {})
            name = (fn.get("name") or "").lower() if isinstance(fn, dict) else ""
            return _TOOL_ORDER_PRIORITY.get(name, 99)
    return 99


# ── JSON 校验 ──────────────────────────────────────────────────────────────

def validate_tool_call_args(tool_name: str, args_json: str) -> dict[str, Any]:
    """校验 tool call 的 JSON arguments 是否有效。

    Args:
        tool_name: 工具名称。
        args_json: JSON 参数字符串。

    Returns:
        {"valid": bool, "args": dict|None, "error": str}
    """
    if not args_json or not args_json.strip():
        return {"valid": False, "args": None, "error": "Empty arguments string"}

    try:
        parsed = json.loads(args_json)
        if not isinstance(parsed, dict):
            return {"valid": False, "args": None, "error": "Arguments must be a JSON object"}
        return {"valid": True, "args": parsed, "error": ""}
    except json.JSONDecodeError as e:
        return {"valid": False, "args": None, "error": f"JSON parse error: {e}"}


# ── 工具调用规范化 ─────────────────────────────────────────────────────────

def normalize_tool_call(tool_call: dict) -> dict:
    """规范化单个 tool_call 的格式。

    确保 tool_call 具有 OpenCode 期望的所有必要字段。

    Args:
        tool_call: 原始 tool_call dict。

    Returns:
        规范化后的 tool_call dict。
    """
    result = dict(tool_call)

    # Ensure type field
    if "type" not in result:
        result["type"] = "function"

    # Ensure function block
    if "function" not in result:
        result["function"] = {}

    fn = result["function"]
    if not isinstance(fn, dict):
        result["function"] = {}

    # Ensure name is valid
    name = result["function"].get("name", "")
    if not name or not isinstance(name, str):
        # Try to infer from id
        result["function"]["name"] = "invalid"

    # Try to repair arguments JSON
    args = result["function"].get("arguments", "{}")
    if isinstance(args, str) and args.strip():
        repaired, was_fixed = repair_tool_call_json(args)
        if was_fixed:
            result["function"]["arguments"] = repaired
    elif not args:
        result["function"]["arguments"] = "{}"

    return result


def normalize_tool_calls_in_chunk(chunk: dict) -> dict:
    """规范化 chunk 中所有 tool_calls 的格式。

    Args:
        chunk: SSE chunk dict。

    Returns:
        规范化后的 chunk。
    """
    choices = chunk.get("choices")
    if not choices:
        return chunk

    new_choices = []
    modified = False
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        delta = choice.get("delta") or {}
        tool_calls = delta.get("tool_calls") or []

        normalized_calls = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                normalized = normalize_tool_call(tc)
                normalized_calls.append(normalized)
                if normalized != tc:
                    modified = True
            else:
                normalized_calls.append(tc)

        if tool_calls:
            new_choices.append({
                **choice,
                "delta": {**delta, "tool_calls": normalized_calls},
            })
        else:
            new_choices.append(choice)

    if modified:
        _log.debug("Normalized tool calls in SSE chunk")
        return {**chunk, "choices": new_choices}
    return chunk


# Backend classification and tool hints are now in opencode_tool_patterns.py
# Re-exported at top of this module for backward compatibility.
