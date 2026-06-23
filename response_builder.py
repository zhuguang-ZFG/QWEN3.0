"""response_builder.py — 响应格式构建函数

提供 OpenAI ChatCompletion 格式（流式/非流式）和 Anthropic Messages 格式的响应构建。
提取自 server.py，供各模块独立引用。
"""

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncGenerator

from lima_constants import MODEL_ID


# ── 工具函数 ─────────────────────────────────────────────────────────────────────


def make_chat_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


# ── OpenAI ChatCompletion 格式 ───────────────────────────────────────────────────


def estimate_token_count(text: str) -> int:
    """Rough token estimate when provider usage is unavailable."""
    if not text:
        return 0
    cn_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    other_chars = len(text) - cn_chars
    return max(1, cn_chars // 2 + other_chars // 4)


def build_usage(prompt_text: str, completion_text: str) -> dict[str, int]:
    prompt_tokens = estimate_token_count(prompt_text)
    completion_tokens = estimate_token_count(completion_text)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def build_response(
    chat_id: str,
    content: str,
    backend: str,
    total_ms: int,
    *,
    prompt_text: str = "",
) -> dict:
    """构建 OpenAI ChatCompletion 非流式响应格式。"""
    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": build_usage(prompt_text, content),
        "system_fingerprint": f"router_{backend}",
        "x_lima_meta": {"backend": backend, "total_ms": total_ms},
    }


def build_stream_chunk(chat_id: str, content: str, finish: bool = False) -> str:
    """构建 SSE 流式 chunk。"""
    delta = {} if finish else {"content": content}
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{"index": 0, "delta": delta if not finish else {}, "finish_reason": "stop" if finish else None}],
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


# ── Anthropic Messages 格式 ──────────────────────────────────────────────────────


def build_anthropic_response(
    msg_id: str,
    content: str,
    backend: str,
    model: str = MODEL_ID,
    *,
    prompt_text: str = "",
) -> dict:
    """构建 Anthropic Messages API 响应格式。"""
    usage = build_usage(prompt_text, content)
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": usage["prompt_tokens"], "output_tokens": usage["completion_tokens"]},
    }


# ── 消息提取 ─────────────────────────────────────────────────────────────────────


def extract_query(messages) -> str:
    """从 messages 列表提取最后一条 user 消息作为 query。
    接受 Pydantic Message 列表或 dict 列表。
    """
    for msg in reversed(messages):
        role = msg.role if hasattr(msg, "role") else msg.get("role", "")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if role == "user":
            return content
    if messages:
        last = messages[-1]
        return last.content if hasattr(last, "content") else last.get("content", "")
    return ""


def messages_to_dicts(messages) -> list[dict]:
    """将 Pydantic Message 列表转为 dict 列表，用于传递完整上下文。"""
    return [
        {
            "role": m.role if hasattr(m, "role") else m.get("role", ""),
            "content": m.content if hasattr(m, "content") else m.get("content", ""),
        }
        for m in messages
        if (m.role if hasattr(m, "role") else m.get("role", "")) in ("user", "assistant")
    ]


# ── 文本分割 ─────────────────────────────────────────────────────────────────────


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？\n.!?])")


def _split_sentences(text: str) -> list[str]:
    """将文本按句子/段落分割为流式 chunk。"""
    if not text:
        return [""]
    parts = [part for part in _SENTENCE_SPLIT_RE.split(text) if part]
    return parts or [text]


async def stream_sentences(chat_id: str, content: str) -> AsyncGenerator[str, None]:
    """Yield sentence chunks followed by finish markers."""
    for sentence in _split_sentences(content):
        yield build_stream_chunk(chat_id, sentence)
        await asyncio.sleep(0.02)
    yield build_stream_chunk(chat_id, "", finish=True)
    yield "data: [DONE]\n\n"
