"""Anthropic SSE helpers for vision short-circuit responses."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any


def anthropic_vision_messages(raw_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vision_msgs: list[dict[str, Any]] = []
    for msg in raw_messages:
        if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
            continue
        content = msg.get("content", "")
        if not isinstance(content, list):
            vision_msgs.append({"role": msg["role"], "content": content})
            continue
        openai_blocks = []
        for block in content:
            if block.get("type") == "text":
                openai_blocks.append({"type": "text", "text": block.get("text", "")})
            elif block.get("type") == "image":
                source = block.get("source", {})
                if source.get("type") == "base64":
                    media_type = source.get("media_type", "image/jpeg")
                    data = source.get("data", "")
                    openai_blocks.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{data}"},
                        }
                    )
            else:
                openai_blocks.append(block)
        vision_msgs.append({"role": msg["role"], "content": openai_blocks})
    return vision_msgs


async def vision_anthropic_stream(content_text: str, req_model: str):
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    yield (
        "event: message_start\n"
        f"data: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'model': req_model, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': 10, 'output_tokens': 0}}})}\n\n"
    )
    yield (
        "event: content_block_start\n"
        f"data: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    )
    chunk_size = 30
    for i in range(0, len(content_text), chunk_size):
        chunk = content_text[i:i + chunk_size]
        yield (
            "event: content_block_delta\n"
            f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': chunk}}, ensure_ascii=False)}\n\n"
        )
        await asyncio.sleep(0.01)
    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    yield (
        "event: message_delta\n"
        f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': len(content_text) // 4}})}\n\n"
    )
    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
