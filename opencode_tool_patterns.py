"""OpenCode tool call patterns, regex helpers, and backend classification.

Extracted from opencode_tool_splitter.py to keep that module under 300 lines.
Contains:
  1. Regex patterns for JSON repair
  2. repair_tool_call_json() -- fix malformed tool call JSON
  3. build_sequential_tool_prompt() / inject_tool_ordering_hint() -- weak backend hints
  4. Backend classification (weak/strong tool backends)

Source references:
  - opencode-source/packages/opencode/src/tool/registry.ts (builtin tools)
  - opencode-source/packages/opencode/src/tool/tool.ts (InvalidArgumentsError)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── OpenCode 内置工具列表 ──────────────────────────────────────────────────
# From registry.ts L245-262

_OPENCODE_BUILTIN_TOOLS = frozenset(
    {
        "invalid",
        "question",
        "shell",
        "read",
        "glob",
        "grep",
        "edit",
        "write",
        "task",
        "webfetch",
        "todo_write",
        "web_search",
        "skill",
        "apply_patch",
        "lsp",
        "plan_enter",
        "plan_exit",
    }
)

# ── 工具依赖顺序 ──────────────────────────────────────────────────────────
# 某些工具应该在其他工具之前调用（如 read 先于 write）

_TOOL_ORDER_PRIORITY: dict[str, int] = {
    "read": 0,
    "glob": 0,
    "grep": 0,  # 信息获取最先
    "task": 1,
    "todo_write": 1,  # 规划和子任务
    "webfetch": 2,
    "web_search": 2,
    "lsp": 2,  # 外部信息
    "shell": 3,  # 执行/测试
    "question": 4,  # 向用户提问
    "edit": 5,
    "write": 5,
    "apply_patch": 5,  # 文件修改最后
    "skill": 6,
    "plan_enter": 6,
    "plan_exit": 6,  # 元操作
}


# ── JSON 修复正则 ─────────────────────────────────────────────────────────

# 缺少引号的 key (e.g. {key: "value"} → {"key": "value"})
_RE_UNQUOTED_KEY = re.compile(r"([{,]\s*)([a-zA-Z_]\w*)(\s*:)")

# Trailing comma before } or ]
_RE_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

# 单引号替代双引号
_RE_SINGLE_QUOTE_KEY = re.compile(r"'([^']*)'(\s*:)")

# 缺少逗号分隔
_RE_MISSING_COMMA = re.compile(r'"\s*\n\s*"')

# Python None/True/False → JSON null/true/false
_RE_PYTHON_NONE = re.compile(r"\bNone\b")
_RE_PYTHON_TRUE = re.compile(r"\bTrue\b")
_RE_PYTHON_FALSE = re.compile(r"\bFalse\b")


# ── JSON 修复 ──────────────────────────────────────────────────────────────


def repair_tool_call_json(args_json: str) -> tuple[str, bool]:
    """尝试修复常见的 JSON arguments 格式错误。

    Args:
        args_json: 可能损坏的 JSON 字符串。

    Returns:
        (repaired_json, was_repaired) — 修复后的 JSON 和是否进行了修复。
    """
    if not args_json or not args_json.strip():
        return args_json, False

    original = args_json
    repaired = args_json

    # 1. Python literals → JSON
    repaired = _RE_PYTHON_NONE.sub("null", repaired)
    repaired = _RE_PYTHON_TRUE.sub("true", repaired)
    repaired = _RE_PYTHON_FALSE.sub("false", repaired)

    # 2. Single quotes → double quotes (carefully, only for keys)
    repaired = _RE_SINGLE_QUOTE_KEY.sub(r'"\1"\2', repaired)

    # 3. Unquoted keys → quoted keys (preserve surrounding syntax)
    repaired = _RE_UNQUOTED_KEY.sub(r'\1"\2"\3', repaired)

    # 4. Trailing commas
    repaired = _RE_TRAILING_COMMA.sub(r"\1", repaired)

    # 5. Try to fix truncated JSON (missing closing brace)
    if repaired.strip().endswith(",") or (repaired.count("{") > repaired.count("}")):
        # Add missing closing braces
        missing = repaired.count("{") - repaired.count("}")
        repaired = repaired.rstrip().rstrip(",") + ("}" * missing)

    # Validate the repaired JSON
    try:
        json.loads(repaired)
        was_repaired = repaired != original
        if was_repaired:
            _log.info("Repaired tool call JSON for %d chars", len(original))
        return repaired, was_repaired
    except json.JSONDecodeError:
        pass

    # 6. Last resort: try to extract just the first key-value pair
    try:
        extracted = _extract_first_valid_json(repaired)
        if extracted:
            _log.warning("Extracted partial JSON from malformed tool call args")
            return extracted, True
    except Exception:
        _log.debug("tool_patterns: JSON extraction failed", exc_info=True)

    return original, False


def _extract_first_valid_json(text: str) -> str | None:
    """Try to extract the first valid JSON object from malformed text."""
    # Find the first { and try parsing incremental substrings
    start = text.find("{")
    if start < 0:
        return None
    for end in range(len(text), start + 2, -1):
        try:
            candidate = text[start:end]
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and parsed:
                return candidate
        except json.JSONDecodeError:
            continue
    return None


# ── 弱后端提示注入 ─────────────────────────────────────────────────────────


def build_sequential_tool_prompt(tools: list[dict] | None = None) -> str:
    """构建弱后端专用的"逐个调用工具"提示文本。

    注入到 system prompt 中，防止弱后端尝试并行调用。

    Args:
        tools: 可用的工具定义列表。

    Returns:
        提示文本。
    """
    lines = [
        "\n## CRITICAL: Tool Call Rules for This Session",
        "- You may call tools, but you MUST call them ONE AT A TIME.",
        "- Do NOT attempt to call multiple tools in a single response.",
        "- Wait for each tool result before calling the next tool.",
        "- This ensures correct execution order and prevents errors.",
    ]

    if tools:
        # Provide ordering guidance
        read_tools = []
        edit_tools = []
        for t in tools:
            name = ""
            if isinstance(t, dict):
                fn = t.get("function", {})
                name = fn.get("name", "") if isinstance(fn, dict) else ""
            if not name:
                continue
            prio = _TOOL_ORDER_PRIORITY.get(name, 99)
            if prio <= 1:
                read_tools.append(name)
            elif prio <= 5:
                edit_tools.append(name)

        if read_tools:
            lines.append(f"- Recommended first: read/gather info via " + ", ".join(f"`{t}`" for t in read_tools))
        if edit_tools:
            lines.append(f"- Then modify: " + ", ".join(f"`{t}`" for t in edit_tools))

    lines.append(
        "- If you're unsure which tool to use next, explain your reasoning "
        "briefly, then call the single most appropriate tool."
    )
    return "\n".join(lines)


def inject_tool_ordering_hint(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> list[dict]:
    """注入工具调用顺序建议到 system prompt。

    Args:
        messages: 消息列表。
        tools: 可用工具列表。

    Returns:
        注入后的消息列表。
    """
    hint = _build_ordering_hint(tools)
    if not hint:
        return list(messages)

    result = list(messages)
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                result[i] = {**msg, "content": content.rstrip() + "\n" + hint}
            elif isinstance(content, list):
                result[i] = {
                    **msg,
                    "content": content + [{"type": "text", "text": hint}],
                }
            return result
    result.insert(0, {"role": "system", "content": hint})
    return result


def _build_ordering_hint(tools: list[dict] | None) -> str:
    """Build a concise tool ordering hint."""
    if not tools:
        return ""

    lines = ["\n## Tool Usage Order (follow this sequence)"]

    priority_groups: dict[int, list[str]] = {}
    for t in tools:
        if not isinstance(t, dict):
            continue
        fn = t.get("function", {})
        name = fn.get("name", "") if isinstance(fn, dict) else ""
        if not name:
            continue
        prio = _TOOL_ORDER_PRIORITY.get(name, 99)
        priority_groups.setdefault(prio, []).append(name)

    group_labels = {
        0: "🔍 First: Gather information",
        1: "📋 Then: Plan your approach",
        2: "🌐 Then: Search external sources",
        3: "⚡ Then: Execute commands",
        4: "❓ Then: Ask the user if needed",
        5: "✏️  Finally: Modify files",
    }

    for prio in sorted(priority_groups.keys()):
        label = group_labels.get(prio, f"📌 Other tools")
        names = priority_groups[prio]
        lines.append(f"{label}: {', '.join(f'`{n}`' for n in sorted(names))}")

    return "\n".join(lines)


# ── 弱后端后端分类 ─────────────────────────────────────────────────────────

# 已知无法正确处理并行工具调用的后端
_WEAK_TOOL_BACKENDS: set[str] = {
    "groq_gptoss",
    "groq_gptoss_20b",
    "groq_llama70b",
    "groq_qwen32b",
    "groq_llama4",
    "cerebras_gptoss",
    "mistral_small",
    "google_flash_lite",
    "google_flash",
    "cfai_llama70b",
    "cfai_llama4",
    "cf_qwen3_30b",
    "github_gpt4o_mini",
    "deepinfra_llama4",
}

# 已知可以正确处理并行工具调用的后端
_STRONG_TOOL_BACKENDS: set[str] = {
    "cf_qwen_coder",
    "cfai_qwen_coder",
    "scnet_ds_flash",
    "scnet_ds_pro",
    "scnet_qwen235b",
    "scnet_qwen30b",
    "nvidia_qwen35_coder",
    "nvidia_deepseek_v4",
    "github_gpt4o",
    "github_codestral",
    "mistral_large",
    "mistral_devstral",
    "kimi",
    "cf_kimi_k26",
    "cf_deepseek_r1",
    "cfai_deepseek_r1",
}


def needs_tool_split(backend: str) -> bool:
    """判断后端是否需要工具调用拆分（弱后端）。"""
    if backend in _STRONG_TOOL_BACKENDS:
        return False
    if backend in _WEAK_TOOL_BACKENDS:
        return True
    return False  # Unknown: assume strong


def should_inject_sequential_hint(backend: str) -> bool:
    """判断是否应注入"逐个调用"提示。"""
    return needs_tool_split(backend)
