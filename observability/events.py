"""LiMa Event Model - internal, typed, sanitized events for observability.

Events are designed to be safe for logging, metrics, and auditing. Raw prompts,
keys, cookies, file bodies, and similar private values are redacted at event
construction time.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field

_SENSITIVE_METADATA_KEYS = (
    "prompt",
    "message",
    "messages",
    "api_key",
    "apikey",
    "key",
    "token",
    "cookie",
    "password",
    "secret",
    "authorization",
    "file_body",
    "body",
)


def _hash_session(session_id: str) -> str:
    if not session_id:
        return ""
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


def _make_request_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class LiMaEvent:
    event_type: str
    timestamp: float = field(default_factory=time.time)
    request_id: str = field(default_factory=_make_request_id)
    session_id_hash: str = ""
    backend: str = ""
    route_reason: str = ""
    latency_ms: float = 0.0
    failure_class: str = ""
    quality_score: float = -1.0
    cost_class: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.route_reason = _sanitize_text(self.route_reason)
        self.failure_class = _sanitize_label(self.failure_class)
        self.cost_class = _sanitize_label(self.cost_class)
        self.metadata = _sanitize_metadata(self.metadata)


def request_start_event(request_id: str = "", session_id: str = "") -> LiMaEvent:
    return LiMaEvent(
        event_type="request_start",
        request_id=request_id or _make_request_id(),
        session_id_hash=_hash_session(session_id),
    )


def request_end_event(request_id: str, latency_ms: float, success: bool) -> LiMaEvent:
    return LiMaEvent(
        event_type="request_end",
        request_id=request_id,
        latency_ms=latency_ms,
        failure_class="" if success else "request_failed",
    )


def backend_call_event(
    request_id: str,
    backend: str,
    route_reason: str = "",
    session_id: str = "",
    latency_ms: float = 0.0,
) -> LiMaEvent:
    return LiMaEvent(
        event_type="backend_call",
        request_id=request_id,
        backend=backend,
        route_reason=route_reason,
        latency_ms=latency_ms,
        session_id_hash=_hash_session(session_id),
    )


def backend_error_event(
    request_id: str,
    backend: str,
    failure_class: str,
    latency_ms: float = 0.0,
) -> LiMaEvent:
    return LiMaEvent(
        event_type="backend_error",
        request_id=request_id,
        backend=backend,
        failure_class=failure_class,
        latency_ms=latency_ms,
    )


def route_decision_event(
    request_id: str,
    backend: str,
    reason: str,
    candidates: list[str] | None = None,
) -> LiMaEvent:
    return LiMaEvent(
        event_type="route_decision",
        request_id=request_id,
        backend=backend,
        route_reason=reason,
        metadata={"candidates": candidates[:5] if candidates else []},
    )


def quality_result_event(
    request_id: str,
    backend: str,
    score: float,
    passed: bool,
) -> LiMaEvent:
    return LiMaEvent(
        event_type="quality_result",
        request_id=request_id,
        backend=backend,
        quality_score=score,
        failure_class="" if passed else "quality_fail",
    )


def key_pool_event(
    provider: str,
    event: str,
    details: str = "",
) -> LiMaEvent:
    return LiMaEvent(
        event_type="key_pool_event",
        backend=provider,
        route_reason=event,
        metadata={"details": details},
    )


def token_usage_event(
    backend: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_class: str,
) -> LiMaEvent:
    return LiMaEvent(
        event_type="token_usage",
        backend=backend,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_class=cost_class,
    )


def _sanitize_label(value: str) -> str:
    return "".join(ch for ch in _sanitize_text(value) if ch.isalnum() or ch in "._:-")[:80]


def _sanitize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    try:
        from session_memory.redact import sanitize_for_display

        return sanitize_for_display(text)
    except ImportError:
        return _fallback_redact(text)


def _sanitize_metadata(value: object) -> object:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                cleaned[key_text] = "[REDACTED]"
            else:
                cleaned[key_text] = _sanitize_metadata(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value[:20]]
    if isinstance(value, tuple):
        return tuple(_sanitize_metadata(item) for item in value[:20])
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_text(value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_METADATA_KEYS)


def _fallback_redact(text: str) -> str:
    lowered = text.lower()
    if "bearer " in lowered or "sk-" in lowered or "cookie" in lowered:
        return "[REDACTED]"
    return text
