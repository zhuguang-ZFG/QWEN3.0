"""OpenCode SSE chunk adaptation helpers."""

from __future__ import annotations

import json
import logging
import time

_log = logging.getLogger(__name__)


def rewrite_sse_model(line: str, model: str, chat_id: str, backend: str = "") -> str:
    if not line.startswith("data: "):
        return line
    payload = line[6:].strip()
    if payload == "[DONE]":
        return line
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return line
    if not isinstance(chunk, dict):
        return line
    chunk["model"] = model
    if chat_id:
        chunk["id"] = chat_id
    chunk = _normalize_protocol(chunk)
    chunk = _passthrough_reasoning(chunk, backend)
    chunk = _normalize_tool_calls(chunk)
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def read_timeout_for(cfg: dict) -> float:
    backend_timeout = float(cfg.get("timeout", 90))
    return max(backend_timeout, _direct_stream_read_timeout())


def content_chunk(chat_id: str, model: str, content: str, *, finish: bool = False) -> str:
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {} if finish else {"role": "assistant", "content": content},
            "finish_reason": "stop" if finish else None,
        }],
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def has_meaningful_delta(line: str) -> bool:
    delta = _delta(line)
    return bool(delta.get("content") or delta.get("tool_calls") or delta.get("reasoning_content"))


def content_delta(line: str) -> str:
    content = _delta(line).get("content")
    return content if isinstance(content, str) else ""


def _delta(line: str) -> dict:
    if not line.startswith("data: "):
        return {}
    payload = line[6:].strip()
    if payload == "[DONE]":
        return {}
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    choice = (chunk.get("choices") or [{}])[0]
    return choice.get("delta") or {}


def _direct_stream_read_timeout() -> float:
    from opencode_config import OPENCODE_DIRECT_STREAM_READ_TIMEOUT

    return OPENCODE_DIRECT_STREAM_READ_TIMEOUT


def _normalize_protocol(chunk: dict) -> dict:
    try:
        from opencode_protocol_adapter import normalize_sse_chunk
    except ImportError:
        _log.warning("opencode protocol adapter not available")
        return chunk
    try:
        normalized = normalize_sse_chunk(chunk)
        # Debug log when Anthropic format is detected
        if chunk.get("type") in ("message_start", "content_block_delta"):
            _log.info("[SSE] Anthropic format detected, converted to OpenAI")
        return normalized
    except Exception as e:
        _log.warning("opencode protocol adapter failed: %s", e, exc_info=True)
        return chunk


def _passthrough_reasoning(chunk: dict, backend: str) -> dict:
    try:
        from opencode_reasoning_bridge import passthrough_reasoning_content
    except ImportError:
        _log.debug("opencode reasoning bridge not available")
        return chunk
    try:
        return passthrough_reasoning_content(chunk, backend)
    except Exception:
        _log.debug("opencode reasoning bridge failed", exc_info=True)
        return chunk


def _normalize_tool_calls(chunk: dict) -> dict:
    try:
        from opencode_tool_splitter import normalize_tool_calls_in_chunk
    except ImportError:
        _log.debug("opencode tool splitter not available")
        return chunk
    try:
        return normalize_tool_calls_in_chunk(chunk)
    except Exception:
        _log.debug("opencode tool splitter failed", exc_info=True)
        return chunk
