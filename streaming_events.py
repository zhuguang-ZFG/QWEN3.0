"""Streaming Event Protocol — typed SSE events for LiMa progress streams.

Defines a vendor-neutral event contract for:
    - Chat token streaming (token)
    - Tool call lifecycle (tool_start / tool_delta / tool_end)
    - Warnings and errors (warning / error)
    - Stream lifecycle (done)
    - Audit correlation (audit_ref)

Each event type has a typed dataclass and a standardized SSE serializer.
Compatible with OpenAI SSE format and Anthropic content_block events.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class StreamEventType(str, Enum):
    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_DELTA = "tool_delta"
    TOOL_END = "tool_end"
    WARNING = "warning"
    ERROR = "error"
    DONE = "done"
    AUDIT_REF = "audit_ref"


@dataclass
class StreamEvent:
    event: StreamEventType | str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.event, StreamEventType):
            self.event = StreamEventType(self.event)
        if self.event != StreamEventType.TOKEN:
            self.data = _sanitize_data(self.data)

    def to_sse(self) -> str:
        payload = {
            "id": self.id,
            "event": self.event.value,
            "data": self.data,
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def to_openai_chunk(self, model: str = "lima") -> str:
        """Render as OpenAI-compatible SSE chunk."""
        if self.event == StreamEventType.TOKEN:
            chunk = {
                "id": f"chatcmpl-{self.id}",
                "object": "chat.completion.chunk",
                "created": int(self.timestamp),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": self.data.get("text", "")},
                    "finish_reason": None,
                }],
            }
        elif self.event == StreamEventType.DONE:
            chunk = {
                "id": f"chatcmpl-{self.id}",
                "object": "chat.completion.chunk",
                "created": int(self.timestamp),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": self.data.get("reason", "stop"),
                }],
            }
        else:
            return self.to_sse()
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


# ── Factory helpers ─────────────────────────────────────────────────────────

def token_event(text: str) -> StreamEvent:
    return StreamEvent(event=StreamEventType.TOKEN, data={"text": text})


def tool_start_event(tool_name: str, tool_id: str = "", input_schema: dict | None = None) -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.TOOL_START,
        data={"tool_name": tool_name, "tool_id": tool_id,
              "input": input_schema or {}},
    )


def tool_delta_event(tool_id: str, delta: str) -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.TOOL_DELTA,
        data={"tool_id": tool_id, "delta": delta},
    )


def tool_end_event(tool_id: str, output: str = "", ok: bool = True) -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.TOOL_END,
        data={"tool_id": tool_id, "output": output, "ok": ok},
    )


def warning_event(message: str, code: str = "") -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.WARNING,
        data={"message": message, "code": code},
    )


def error_event(message: str, code: str = "", recoverable: bool = False) -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.ERROR,
        data={"message": message, "code": code, "recoverable": recoverable},
    )


def done_event(reason: str = "stop") -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.DONE,
        data={"reason": reason},
    )


def audit_ref_event(audit_id: str) -> StreamEvent:
    return StreamEvent(
        event=StreamEventType.AUDIT_REF,
        data={"audit_id": audit_id},
    )


def build_usage_chunk(request_id: str, usage: dict, model: str = "lima") -> str:
    """Build an OpenAI-compatible SSE chunk containing usage statistics.

    Emitted as the final data chunk before [DONE] when stream_options.include_usage
    is requested.  Format matches OpenAI spec:
        {"id":"...","object":"chat.completion.chunk","choices":[...],"usage":{...}}
    """
    chunk = {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": None,
        }],
        "usage": usage,
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


# ── SSE formatting ──────────────────────────────────────────────────────────

def format_sse_done() -> str:
    return "data: [DONE]\n\n"


def is_valid_event_name(name: str) -> bool:
    try:
        StreamEventType(name)
        return True
    except ValueError:
        return False


_SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "authorization",
    "body",
    "cookie",
    "key",
    "password",
    "prompt",
    "secret",
    "token",
)


def _sanitize_text(value: object) -> str:
    text = str(value)
    try:
        from session_memory.redact import sanitize_for_display
        return sanitize_for_display(text)
    except ImportError:
        lowered = text.lower()
        if "bearer " in lowered or "sk-" in lowered or "cookie" in lowered:
            return "[REDACTED]"
        return text


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_KEYS)


def _sanitize_data(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(str(key)) else _sanitize_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_data(item) for item in value[:50]]
    if isinstance(value, tuple):
        return tuple(_sanitize_data(item) for item in value[:50])
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_text(value)
