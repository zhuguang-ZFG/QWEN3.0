"""opencode_protocol_adapter.py — OpenCode 协议源码级适配。

从 opencode-source 源码分析 OpenCode 对 OpenAI Chat Completions 协议的
具体期望，处理弱后端返回的非标准响应格式。

核心功能:
  1. finish_reason 标准化映射（20+ 后端变体 → 标准值）
  2. max_tokens 协商：在 model list 中返回 maxOutputTokens
  3. 流式中断优雅降级：后端断开时不返回 500，而是返回部分内容
  4. 非标准 usage 字段补充

参考:
  - opencode-source/packages/llm/src/protocols/openai-chat.ts (mapFinishReason L287-293)
  - opencode-source/packages/llm/src/protocols/gemini.ts (mapFinishReason L309-323)
  - opencode-source/packages/llm/src/schema.ts (FinishReason type)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── Standard finish_reason values (OpenCode schema) ──────────────────────────
# From opencode-source/packages/llm/src/schema.ts:
#   "stop" | "length" | "content-filter" | "tool-calls" | "error" | "other" | "unknown"
_STANDARD_REASONS = frozenset({
    "stop", "length", "content-filter", "tool-calls",
    "error", "other", "unknown",
})

# ── finish_reason 映射表 ────────────────────────────────────────────────────
# 将各种非标准后端返回的 finish_reason 映射为标准值
_FINISH_REASON_MAP: dict[str, str] = {
    # OpenAI variants
    "function_call": "tool-calls",
    "tool_calls": "tool-calls",
    "content_filter": "content-filter",
    "max_tokens": "length",

    # Anthropic variants (when proxied through OpenAI API)
    "end_turn": "stop",
    "stop_sequence": "stop",
    "pause_turn": "stop",
    "refusal": "content-filter",
    "max_output_tokens": "length",

    # Google Gemini variants
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "IMAGE_SAFETY": "content-filter",
    "RECITATION": "content-filter",
    "SAFETY": "content-filter",
    "BLOCKLIST": "content-filter",
    "PROHIBITED_CONTENT": "content-filter",
    "SPII": "content-filter",
    "MALFORMED_FUNCTION_CALL": "error",

    # Bedrock variants
    "content_filtered": "content-filter",
    "guardrail_intervened": "content-filter",

    # DeepSeek variants
    "insufficient_system_resource": "error",

    # Generic fallbacks
    "error": "error",
    "timeout": "error",
    "cancelled": "stop",
    "abort": "stop",
    "interrupt": "stop",
    "done": "stop",
    "finish": "stop",
    "completed": "stop",
    "null": "stop",
    "none": "stop",
    "": "stop",
}


def normalize_finish_reason(reason: str | None) -> str:
    """将非标准 finish_reason 映射为标准值。

    标准值（OpenCode 可识别）:
      stop, length, content-filter, tool-calls, error, other, unknown

    Args:
        reason: 后端返回的原始 finish_reason。

    Returns:
        标准化后的 finish_reason。
    """
    if reason is None:
        return "stop"

    # Already standard
    if reason in _STANDARD_REASONS:
        return reason

    # Direct mapping
    mapped = _FINISH_REASON_MAP.get(reason)
    if mapped:
        return mapped

    # Case-insensitive lookup
    lower = reason.lower()
    mapped = _FINISH_REASON_MAP.get(lower)
    if mapped:
        return mapped

    # Heuristic matching
    if "tool" in lower or "function" in lower:
        return "tool-calls"
    if "len" in lower or "max" in lower or "truncat" in lower:
        return "length"
    if any(w in lower for w in ("filter", "safety", "block", "refus", "recit")):
        return "content-filter"
    if any(w in lower for w in ("error", "fail", "invalid", "malform")):
        return "error"
    if any(w in lower for w in ("stop", "end", "done", "finish", "complet", "cancel", "abort")):
        return "stop"

    _log.debug("Unknown finish_reason: '%s', mapping to 'other'", reason)
    return "other"


def normalize_sse_chunk(chunk: dict) -> dict:
    """规范化 SSE chunk 中的 finish_reason。

    修改传入的 chunk（或返回修改后的副本），确保 choices 中的
    finish_reason 是 OpenCode 可识别的标准值。

    Args:
        chunk: 原始 SSE chunk dict。

    Returns:
        规范化后的 chunk dict。
    """
    choices = chunk.get("choices")
    if not choices:
        return chunk

    modified = False
    new_choices = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        reason = choice.get("finish_reason")
        if reason is not None:
            normalized = normalize_finish_reason(reason)
            if normalized != reason:
                _log.debug(
                    "Normalized finish_reason: '%s' → '%s'",
                    reason, normalized,
                )
                modified = True
                new_choices.append({**choice, "finish_reason": normalized})
            else:
                new_choices.append(choice)
        else:
            new_choices.append(choice)

    if modified:
        return {**chunk, "choices": new_choices}
    return chunk


def normalize_sse_line(line: str) -> str:
    """规范化单条 SSE data: 行中的 finish_reason。

    Parses the JSON in the SSE line, normalizes finish_reason,
    and re-serializes.

    Args:
        line: 原始 SSE 行（如 "data: {...}"）。

    Returns:
        规范化后的 SSE 行。
    """
    if not line.startswith("data: "):
        return line

    # Skip [DONE] marker
    if line.strip() == "data: [DONE]":
        return line

    try:
        data = json.loads(line[6:].strip())
    except (json.JSONDecodeError, TypeError):
        return line

    normalized = normalize_sse_chunk(data)
    return f"data: {json.dumps(normalized, ensure_ascii=False)}\n"


# ── max_tokens / model capabilities negotiation ──────────────────────────────

def build_model_output_limits(model_list: list[dict]) -> list[dict]:
    """为 model list 响应添加 maxOutputTokens 等 OpenCode 需要的字段。

    OpenCode 在 model 选择时会检查:
      - maxOutputTokens: 用于计算 compaction 预算
      - context_window: 用于溢出检测

    Args:
        model_list: 现有的 /v1/models 响应中的 data 列表。

    Returns:
        增强后的 model list。
    """
    for model in model_list:
        model_id = model.get("id", "")
        # Add max_tokens hint for OpenCode
        if "maxOutputTokens" not in model and "max_output_tokens" not in model:
            # Estimate from model name or default
            model["maxOutputTokens"] = _estimate_max_output(model_id)
    return model_list


def _estimate_max_output(model_id: str) -> int:
    """根据模型名称估算最大输出 token 数。"""
    lower = model_id.lower()
    if any(k in lower for k in ("gpt-4", "claude", "gemini-2")):
        return 16384
    if any(k in lower for k in ("deepseek", "qwen", "llama")):
        return 8192
    if any(k in lower for k in ("coder", "codestral")):
        return 16384
    return 4096


# ── Stream interruption graceful handling ────────────────────────────────────

def is_stream_truncated(
    accumulated_content: str,
    received_finish: bool,
    last_chunk_error: str = "",
) -> bool:
    """检测流式响应是否被截断（后端断连但未发送 finish_reason）。

    Args:
        accumulated_content: 已累积的文本内容。
        received_finish: 是否收到了 finish_reason。
        last_chunk_error: 最后一个 chunk 的解析错误（如有）。

    Returns:
        True if the stream appears truncated.
    """
    if received_finish:
        return False

    # If we got some content but no finish, it might be truncated
    if accumulated_content and not received_finish:
        _log.warning(
            "Stream truncated: %d chars, no finish_reason",
            len(accumulated_content),
        )
        return True

    return False


def build_graceful_finish_chunk(
    model: str = "lima-1.3",
    chat_id: str = "",
    finish_reason: str = "stop",
    usage: dict | None = None,
) -> str:
    """构建优雅终止的 SSE 完成 chunk。

    当后端流断开但没有发送 finish_reason 时，补发一个完成事件。

    Args:
        model: 模型名称。
        chat_id: 聊天 ID。
        finish_reason: 补发的 finish_reason。
        usage: 可选的 usage 信息。

    Returns:
        SSE 格式的完成 chunk 字符串（含 SSE 换行）。
    """
    import time

    chunk: dict[str, Any] = {
        "id": chat_id or "chatcmpl-graceful",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": finish_reason,
        }],
    }

    if usage:
        chunk["usage"] = usage

    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


# ── Detect non-standard backends that need special handling ──────────────────

_NON_STANDARD_BACKEND_PATTERNS = [
    # Backends known to return non-standard finish_reason
    (re.compile(r"scnet", re.I), "scnet_free"),
    (re.compile(r"chinamobile", re.I), "china_mobile"),
    (re.compile(r"free_model", re.I), "free_model_dev"),
    (re.compile(r"kimi", re.I), "kimi_moonshot"),
]


def needs_finish_reason_normalization(backend: str) -> bool:
    """检测后端是否需要 finish_reason 标准化。

    已知返回非标准 finish_reason 的后端返回 True。
    """
    for pattern, _ in _NON_STANDARD_BACKEND_PATTERNS:
        if pattern.search(backend):
            return True
    return False


# ── Parallel tool call detection ─────────────────────────────────────────────

def detect_multiple_tool_calls(chunk: dict) -> list[dict]:
    """检测 SSE chunk 中是否包含多个并行 tool_calls。

    OpenCode 支持一次返回多个 tool_calls（如同时 read 和 grep）。
    弱后端可能不支持并行返回，需要检测和适配。

    Returns:
        提取的 tool_calls 列表。
    """
    choices = chunk.get("choices") or []
    all_tool_calls: list[dict] = []

    for choice in choices:
        delta = choice.get("delta") or {}
        tool_calls = delta.get("tool_calls") or []
        for tc in tool_calls:
            if isinstance(tc, dict):
                all_tool_calls.append(tc)

    return all_tool_calls
