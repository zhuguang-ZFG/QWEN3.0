"""Anthropic SSE frame helpers for routes/anthropic_stream (CQ-099)."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator


def new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:24]}"


def sse_message_start(model: str, msg_id: str | None = None) -> str:
    message_id = msg_id or new_message_id()
    payload = {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 0},
        },
    }
    return f"event: message_start\ndata: {json.dumps(payload)}\n\n"


def sse_content_block_start() -> str:
    payload = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }
    return f"event: content_block_start\ndata: {json.dumps(payload)}\n\n"


def sse_text_delta(text: str) -> str:
    payload = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": text},
    }
    return f"event: content_block_delta\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_message_end(output_chars: int) -> tuple[str, str, str]:
    stop = f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    delta = (
        "event: message_delta\n"
        f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': output_chars // 4}})}\n\n"
    )
    end = f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
    return stop, delta, end


async def stream_text_as_sse(
    content: str,
    model: str,
    *,
    chunk_size: int = 20,
    sleep_sec: float = 0.01,
) -> AsyncIterator[str]:
    msg_id = new_message_id()
    yield sse_message_start(model, msg_id)
    yield sse_content_block_start()
    for index in range(0, len(content), chunk_size):
        yield sse_text_delta(content[index : index + chunk_size])
        if sleep_sec:
            await asyncio.sleep(sleep_sec)
    stop, delta, end = sse_message_end(len(content))
    yield stop
    yield delta
    yield end
