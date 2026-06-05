"""opencode_truncate.py — 工具输出截断保护。

复刻 OpenCode tool/truncate.ts 的 Truncate.output() (L86-142)。

OpenCode 对 tool 输出做截断保护，防止超大输出撑爆模型上下文：
- MAX_LINES = 2000, MAX_BYTES = 50KB
- 方向: head (保留前部) 或 tail (保留后部)
- 超限时: 返回预览 + 截断提示 (含原始字节/行数统计)

LiMa 服务端在构建请求时，对 messages 中过大的 tool result 内容做截断，
避免下游模型 OOM 或浪费 token 预算。

源码参考:
  - opencode-source/packages/opencode/src/tool/truncate.ts
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ── OpenCode 源码常量 (truncate.ts:5-8) ─────────────────────────────────────
MAX_LINES = 2000
MAX_BYTES = 50 * 1024  # 50 KB

# 截断提示模板 (truncate.ts:98-105)
_TRUNCATE_HINT_TEMPLATE = (
    "\n\n... [{direction} truncated: {total_lines} lines, {total_bytes} bytes total. "
    "Showing {shown_lines} lines. "
    "Full output saved. Use Grep/Read to search the full output if needed.]"
)


def truncate_output(
    text: str,
    max_lines: int = MAX_LINES,
    max_bytes: int = MAX_BYTES,
    direction: str = "head",
) -> tuple[str, bool]:
    """截断过大的工具输出文本。

    复刻 Truncate.output() (truncate.ts:86-142)。

    Args:
        text: 原始工具输出文本。
        max_lines: 最大保留行数 (默认 2000)。
        max_bytes: 最大保留字节数 (默认 50KB)。
        direction: 截断方向 — "head" 保留前部, "tail" 保留后部。

    Returns:
        (truncated_text, was_truncated) 元组。
        was_truncated 为 True 表示输出被截断过。
    """
    if not text:
        return text, False

    total_bytes = len(text.encode("utf-8", errors="replace"))
    lines = text.split("\n")
    total_lines = len(lines)

    # 未超限 → 原样返回
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return text, False

    # 字节超限先截断 (在行截断之前，因为 bytes 限制更严格)
    if total_bytes > max_bytes:
        encoded = text.encode("utf-8", errors="replace")
        if direction == "head":
            truncated_bytes = encoded[:max_bytes]
        else:
            truncated_bytes = encoded[-max_bytes:]
        # 解码回字符串 (忽略不完整字符)
        text = truncated_bytes.decode("utf-8", errors="ignore")
        lines = text.split("\n")

    # 行数超限截断
    if len(lines) > max_lines:
        if direction == "head":
            kept = lines[:max_lines]
        else:
            kept = lines[-max_lines:]
        shown_lines = max_lines
    else:
        kept = lines
        shown_lines = len(lines)

    # 重新计算截断后的字节
    result_text = "\n".join(kept)
    result_bytes = len(result_text.encode("utf-8", errors="replace"))

    # 构建截断提示
    hint = _TRUNCATE_HINT_TEMPLATE.format(
        direction=direction,
        total_lines=total_lines,
        total_bytes=total_bytes,
        shown_lines=shown_lines,
    )

    _log.debug(
        "truncated tool output: %d→%d lines, %d→%d bytes (direction=%s)",
        total_lines, shown_lines, total_bytes, result_bytes, direction,
    )

    return result_text + hint, True


def truncate_tool_results_in_messages(
    messages: list[dict],
    max_lines: int = MAX_LINES,
    max_bytes: int = MAX_BYTES,
    direction: str = "head",
) -> list[dict]:
    """遍历 messages，对所有 tool result 内容做截断。

    处理两种格式:
    1. OpenAI 格式: role="tool", content=str
    2. Anthropic 格式: role="user", content=[{type:"tool_result", ...}]

    Args:
        messages: 消息列表。
        max_lines: 最大行数。
        max_bytes: 最大字节数。
        direction: 截断方向。

    Returns:
        截断后的消息列表 (新列表，不修改原始数据)。
    """
    result = []
    truncated_count = 0

    for msg in messages:
        role = msg.get("role", "")

        # ── OpenAI tool result ──
        if role == "tool":
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > max_bytes or (
                isinstance(content, str) and content.count("\n") > max_lines
            ):
                new_content, was_truncated = truncate_output(
                    content, max_lines, max_bytes, direction,
                )
                if was_truncated:
                    truncated_count += 1
                    msg = {**msg, "content": new_content}

        # ── Anthropic tool_result in user messages ──
        elif role == "user" and isinstance(msg.get("content"), list):
            new_blocks = []
            modified = False
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    inner = block.get("content", "")
                    if isinstance(inner, str) and (
                        len(inner) > max_bytes or inner.count("\n") > max_lines
                    ):
                        new_inner, was_truncated = truncate_output(
                            inner, max_lines, max_bytes, direction,
                        )
                        if was_truncated:
                            truncated_count += 1
                            block = {**block, "content": new_inner}
                            modified = True
                    elif isinstance(inner, list):
                        new_inner_blocks = []
                        inner_modified = False
                        for ib in inner:
                            if isinstance(ib, dict) and ib.get("type") == "text":
                                txt = ib.get("text", "")
                                if len(txt) > max_bytes or txt.count("\n") > max_lines:
                                    new_txt, was_truncated = truncate_output(
                                        txt, max_lines, max_bytes, direction,
                                    )
                                    if was_truncated:
                                        truncated_count += 1
                                        ib = {**ib, "text": new_txt}
                                        inner_modified = True
                            new_inner_blocks.append(ib)
                        if inner_modified:
                            block = {**block, "content": new_inner_blocks}
                            modified = True
                new_blocks.append(block)
            if modified:
                msg = {**msg, "content": new_blocks}

        # ── 普通 assistant text (某些模型把 tool output 放在 assistant 消息) ──
        elif role == "assistant" and isinstance(msg.get("content"), list):
            new_blocks = []
            modified = False
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    inner = block.get("content", "")
                    if isinstance(inner, str) and (
                        len(inner) > max_bytes or inner.count("\n") > max_lines
                    ):
                        new_inner, was_truncated = truncate_output(
                            inner, max_lines, max_bytes, direction,
                        )
                        if was_truncated:
                            truncated_count += 1
                            block = {**block, "content": new_inner}
                            modified = True
                new_blocks.append(block)
            if modified:
                msg = {**msg, "content": new_blocks}

        result.append(msg)

    if truncated_count:
        _log.info("truncated %d tool result(s) in messages", truncated_count)

    return result
