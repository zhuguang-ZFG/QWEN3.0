"""Core protocol constants, errors, and low-level message helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


PROTOCOL_VERSION = "lima-device-v1"

SUPPORTED_UPLINK_TYPES = {
    "hello",
    "heartbeat",
    "transcript",
    "motion_event",
    "device_info",
    "self_check",
    "voiceprint_sample",
    "audio",
}

REQUIRED_MOTION_LIFECYCLE_PHASES = frozenset({"accepted", "running"})
TERMINAL_MOTION_PHASES = frozenset({"done", "failed", "cancelled", "rejected", "stopped"})


class ProtocolError(ValueError):
    """Stable device protocol validation error."""

    def __init__(self, code: str, message: str, request_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_request_id(message: dict[str, Any]) -> str | None:
    value = message.get("request_id")
    return value if isinstance(value, str) and value else None


def _non_empty_string(message: dict[str, Any], field: str) -> str:
    value = message.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError("E_INVALID_MESSAGE", f"{field} must be a non-empty string", _optional_request_id(message))
    return value.strip()


def ensure_object(message: Any) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise ProtocolError("E_INVALID_MESSAGE", "message must be a JSON object")
    return message


def require_type(message: dict[str, Any]) -> str:
    raw_type = message.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ProtocolError("E_INVALID_MESSAGE", "type must be a non-empty string", _optional_request_id(message))
    msg_type = raw_type.strip()
    if msg_type not in SUPPORTED_UPLINK_TYPES:
        raise ProtocolError("E_UNSUPPORTED_TYPE", "message type is not supported", _optional_request_id(message))
    return msg_type
