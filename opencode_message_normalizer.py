"""OpenCode 消息规范化管线 — 移植自 transform.ts normalizeMessages()。

在转发到后端前对消息做与 OpenCode 同等的规范化处理，包括:
- Surrogate 字符清理
- 空消息过滤（Anthropic/Bedrock 兼容）
- toolCallId 规范化（Claude/Mistral 格式要求）
- 消息序列修复（Mistral: tool→user 间插入 assistant）
"""

from __future__ import annotations

import re
from typing import Any

# Surrogate 字符清理正则 — 移植自 transform.ts L25-27
_SURROGATE_RE = re.compile(
    r"[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]",
)


def sanitize_surrogates(text: str) -> str:
    """清理孤儿 surrogate 字符。
    
    某些后端（如 Anthropic）会拒绝包含非法 Unicode 的消息。
    将孤立的 surrogate 替换为 U+FFFD (REPLACEMENT CHARACTER)。
    移植自 transform.ts sanitizeSurrogates()。
    """
    return _SURROGATE_RE.sub("\uFFFD", text)


def _is_anthropic_backend(backend: str) -> bool:
    """检测后端是否为 Anthropic 格式。
    
    支持 backend 名称（含 'anthropic'）或 model 名称（含 'claude'）。
    """
    if not backend:
        return False
    lower = backend.lower()
    return "anthropic" in lower or "claude" in lower


def _is_mistral_backend(backend: str) -> bool:
    """检测后端是否为 Mistral 格式。
    
    支持 backend 名称或 model 名称。
    """
    if not backend:
        return False
    lower = backend.lower()
    return "mistral" in lower or "devstral" in lower or "codestral" in lower


def _sanitize_message_content(msg: dict) -> dict:
    """对单条消息的内容做 surrogate 清理（递归处理）。"""
    content = msg.get("content", "")
    if isinstance(content, str):
        return {**msg, "content": sanitize_surrogates(content)}
    if isinstance(content, list):
        cleaned = []
        for part in content:
            if isinstance(part, dict) and part.get("type") in ("text",):
                cleaned.append({**part, "text": sanitize_surrogates(part.get("text", ""))})
            elif isinstance(part, dict) and part.get("type") == "reasoning":
                cleaned.append({**part, "text": sanitize_surrogates(part.get("text", ""))})
            else:
                cleaned.append(part)
        return {**msg, "content": cleaned}
    return msg


def filter_empty_messages(messages: list[dict]) -> list[dict]:
    """过滤空内容消息（Anthropic/Bedrock 兼容）。
    
    Anthropic 和 Bedrock 拒绝包含空 content 的消息。
    移除 content 为空的字符串消息，以及内容列表全部为空的消息。
    移植自 transform.ts L132-185。
    """
    result: list[dict] = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            if content == "":
                continue
            result.append(msg)
        elif isinstance(content, list):
            filtered = [
                p for p in content
                if not (isinstance(p, dict) and p.get("type") == "text" and not p.get("text"))
            ]
            if not filtered:
                continue
            result.append({**msg, "content": filtered})
        else:
            result.append(msg)
    return result


def normalize_tool_call_ids(messages: list[dict], backend: str) -> list[dict]:
    """按后端要求规范化 toolCallId。
    
    - Anthropic/Claude: 仅允许 [a-zA-Z0-9_-]
    - Mistral: 仅允许 9 位字母数字，不足补零
    
    移植自 transform.ts L187-263。
    """
    if _is_anthropic_backend(backend):
        scrub = lambda _id: re.sub(r"[^a-zA-Z0-9_-]", "_", _id)[:64] if _id else _id
        return _apply_tool_id_scrub(messages, scrub)

    if _is_mistral_backend(backend):
        def _scrub_mistral(_id: str) -> str:
            if not _id:
                return _id
            cleaned = re.sub(r"[^a-zA-Z0-9]", "", _id)
            return cleaned[:9].ljust(9, "0")

        result = _apply_tool_id_scrub(messages, _scrub_mistral)

        # Fix message sequence: tool→user 间插入 assistant "Done."
        # Mistral 拒绝 tool 消息后直接跟 user 消息
        fixed: list[dict] = []
        for i, msg in enumerate(result):
            fixed.append(msg)
            next_msg = result[i + 1] if i + 1 < len(result) else None
            if msg.get("role") == "tool" and next_msg and next_msg.get("role") == "user":
                fixed.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Done."}],
                })
        return fixed

    return messages


def _apply_tool_id_scrub(messages: list[dict], scrub_fn) -> list[dict]:
    """对消息中的 toolCallId 应用清洗函数。"""
    result: list[dict] = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            cleaned = []
            for part in content:
                if isinstance(part, dict) and part.get("toolCallId"):
                    cleaned.append({**part, "toolCallId": scrub_fn(part["toolCallId"])})
                else:
                    cleaned.append(part)
            result.append({**msg, "content": cleaned})
        else:
            result.append(msg)

        # 处理 tool_calls 字段（OpenAI 格式）
        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            fixed_calls = []
            for tc in tool_calls:
                if isinstance(tc, dict) and tc.get("id"):
                    fixed_calls.append({**tc, "id": scrub_fn(tc["id"])})
                else:
                    fixed_calls.append(tc)
            result[-1] = {**result[-1], "tool_calls": fixed_calls}
    return result


def normalize_messages(messages: list[dict], backend: str) -> list[dict]:
    """统一入口：对消息列表做完整的规范化处理。
    
    处理顺序:
    1. Surrogate 字符清理（所有后端）
    2. 空消息过滤（仅 Anthropic 格式后端——但安全无害可通用）
    3. toolCallId 规范化（按后端类型）
    4. 消息序列修复（Mistral）
    
    Args:
        messages: 消息列表，每个元素为 {"role": ..., "content": ...} 格式。
        backend: 目标后端名称或模型名称（用于判断后端类型）。
                 支持 backend 名称（如 'mimo_v2_pro_anthropic'）
                 或 model 名称（如 'claude-3.5-sonnet'）。
    
    Returns:
        规范化后的消息列表（返回新列表，不修改输入）。
    """
    # Step 1: Surrogate 清理
    result = [_sanitize_message_content(m) for m in messages]

    # Step 2: 空消息过滤（安全地应用所有后端）
    result = filter_empty_messages(result)

    # Step 3-4: toolCallId 规范化 + 序列修复
    result = normalize_tool_call_ids(result, backend)

    return result
