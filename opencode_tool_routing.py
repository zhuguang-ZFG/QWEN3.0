"""opencode_tool_routing.py — 工具路由动态切换 + Copilot _noop workaround。

复刻 OpenCode tool/registry.ts 的工具选择逻辑 (L313-324)
和 session/llm/request.ts 的 Copilot _noop workaround (L142-158)。

核心功能:
  1. should_use_apply_patch() — GPT-5+ 使用 apply_patch 替代 edit/write
  2. filter_tools_for_model() — 按模型族过滤工具列表
  3. inject_noop_tool_if_needed() — Copilot 无工具时的 workaround

源码参考:
  - opencode-source/packages/opencode/src/tool/registry.ts (L313-324)
  - opencode-source/packages/opencode/src/session/llm/request.ts (L142-158)
"""

from __future__ import annotations

import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── 工具 ID 常量 (registry.ts) ──────────────────────────────────────────────
# apply_patch 工具 (GPT-5+ 专用)
APPLY_PATCH_TOOL_ID = "apply_patch"
# 传统编辑工具
EDIT_TOOL_IDS = frozenset({"edit", "write", "file_edit", "file_write",
                            "edit_file", "write_file", "create_file",
                            "str_replace", "create"})

# ── GPT-5+ 判定模式 (registry.ts:317-323) ───────────────────────────────────
# usePatch = modelID.includes("gpt-") && !includes("oss") && !includes("gpt-4")
_GPT_PATTERN = re.compile(r"gpt[-_]?", re.IGNORECASE)
_EXCLUDE_OSS_PATTERN = re.compile(r"oss", re.IGNORECASE)
_EXCLUDE_GPT4_PATTERN = re.compile(r"gpt[-_]?4", re.IGNORECASE)


def should_use_apply_patch(model_id: str) -> bool:
    """判断模型是否应使用 apply_patch 替代 edit/write。

    复刻 registry.ts L317-323:
      usePatch = modelID.includes("gpt-")
                 && !modelID.includes("oss")
                 && !modelID.includes("gpt-4")

    Args:
        model_id: 模型标识符 (如 "gpt-5-turbo", "gpt-4o")。

    Returns:
        True 表示应使用 apply_patch 工具组。
    """
    if not model_id:
        return False
    mid = model_id.lower()

    # Must contain "gpt" (with optional separator)
    if not _GPT_PATTERN.search(mid):
        return False

    # Exclude "oss" variants (e.g., "gpt-oss-120b")
    if _EXCLUDE_OSS_PATTERN.search(mid):
        return False

    # Exclude GPT-4 family (gpt-4, gpt-4o, gpt-4-turbo, etc.)
    if _EXCLUDE_GPT4_PATTERN.search(mid):
        return False

    return True


def filter_tools_for_model(
    tools: list[dict],
    model_id: str,
    backend_name: str = "",
) -> list[dict]:
    """根据模型族过滤工具列表。

    复刻 registry.ts L313-324 的工具选择逻辑:
    - GPT-5+: 保留 apply_patch，移除 edit/write
    - 其他模型: 保留 edit/write，移除 apply_patch

    Args:
        tools: 工具定义列表 (OpenAI function 格式)。
        model_id: 模型标识符。
        backend_name: 后端名称 (用于日志)。

    Returns:
        过滤后的工具列表。
    """
    if not tools:
        return tools

    use_patch = should_use_apply_patch(model_id)

    result = []
    removed = 0

    for tool in tools:
        tool_id = _extract_tool_id(tool)
        if not tool_id:
            result.append(tool)
            continue

        tid_lower = tool_id.lower()

        if use_patch:
            # GPT-5+ mode: keep apply_patch, remove edit/write
            if tid_lower in EDIT_TOOL_IDS:
                removed += 1
                continue
        else:
            # Traditional mode: keep edit/write, remove apply_patch
            if tid_lower == APPLY_PATCH_TOOL_ID:
                removed += 1
                continue

        result.append(tool)

    if removed:
        _log.debug(
            "tool routing: model=%s use_patch=%s removed=%d tools backend=%s",
            model_id, use_patch, removed, backend_name,
        )

    return result


def _extract_tool_id(tool: dict) -> str:
    """从工具定义中提取工具 ID。

    支持 OpenAI function 格式: {"type": "function", "function": {"name": "edit"}}
    """
    # OpenAI function format
    fn = tool.get("function")
    if isinstance(fn, dict):
        return fn.get("name", "")
    # Direct name field
    return tool.get("name", "") or tool.get("id", "")


# ── Copilot _noop workaround (request.ts:142-158) ──────────────────────────

_NOOP_TOOL = {
    "type": "function",
    "function": {
        "name": "_noop",
        "description": (
            "Do not call this tool. It exists only to satisfy API requirements "
            "when no other tools are available but tool calls exist in history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you are not calling any real tool.",
                },
            },
            "required": [],
        },
    },
}


def inject_noop_tool_if_needed(
    tools: list[dict] | None,
    messages: list[dict],
    backend_name: str,
) -> list[dict] | None:
    """Copilot _noop 工具注入 workaround。

    复刻 request.ts L142-158:
    当 GitHub Copilot 后端 + 无活跃工具 + 历史消息中有 tool_calls 时，
    注入 _noop 工具避免 API 报错。

    Args:
        tools: 当前工具列表 (可能为 None)。
        messages: 消息列表。
        backend_name: 后端名称。

    Returns:
        注入后的工具列表，或原始 tools (若不需要注入)。
    """
    # Only for Copilot backends
    bn_lower = (backend_name or "").lower()
    if "copilot" not in bn_lower and "github" not in bn_lower:
        return tools

    # Only when no active tools
    if tools and len(tools) > 0:
        return tools

    # Only when history has tool calls
    if not _has_tool_calls_in_history(messages):
        return tools

    _log.info(
        "injecting _noop tool for Copilot backend=%s (history has tool_calls)",
        backend_name,
    )

    result = list(tools) if tools else []
    result.append(dict(_NOOP_TOOL))
    return result


def _has_tool_calls_in_history(messages: list[dict]) -> bool:
    """检测消息历史中是否存在 tool_calls。"""
    for msg in messages:
        # Assistant messages with tool_calls
        if msg.get("tool_calls"):
            return True
        # Tool result messages
        if msg.get("role") == "tool":
            return True
        # Anthropic format: content blocks with tool_use / tool_result
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type", "")
                    if btype in ("tool_use", "tool_result"):
                        return True
    return False
