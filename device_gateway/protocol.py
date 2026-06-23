"""Protocol helpers for LiMa direct device sessions.

This module is a compatibility facade over the split protocol package:
- protocol_core (merged): constants, ProtocolError, and low-level helpers
- protocol_validators: uplink message validators
- protocol_frames: downlink frame builders
- protocol_lifecycle (merged): motion task lifecycle validation
"""

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


def validate_motion_task_lifecycle(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Check that a motion task event sequence is well-formed.

    Returns {"ok": True, "terminal_phase": "done"} or
            {"ok": False, "reason": "...", "missing_phase": "..."}
    """
    if not events:
        return {"ok": False, "reason": "no events recorded", "missing_phase": "accepted"}
    phases = [e.get("phase", "") for e in events]
    terminal = next((p for p in phases if p in TERMINAL_MOTION_PHASES), None)
    if terminal is None:
        return {"ok": False, "reason": "no terminal phase reached", "missing_phase": "done|failed"}
    if terminal == "failed":
        error = None
        for e in reversed(events):
            err = e.get("error") if isinstance(e, dict) else None
            if isinstance(err, dict) and err.get("code"):
                error = err
                break
        if error is None:
            return {"ok": False, "reason": "failed event missing error code"}
        return {"ok": True, "terminal_phase": "failed", "error": error}
    return {"ok": True, "terminal_phase": terminal}


from device_gateway.protocol_frames import (  # noqa: E402
    ack_frame,
    audio_reply_frame,
    build_voiceprint_sample_ack,
    error_frame,
    hello_ack,
    motion_failure_event,
    run_path_dispatch_frame,
    voice_status_frame,
)
from device_gateway.protocol_validators import (  # noqa: E402
    validate_device_info,
    validate_heartbeat,
    validate_hello,
    validate_motion_event,
    validate_self_check,
    validate_transcript,
    validate_uplink,
    validate_voiceprint_sample,
)

__all__ = [
    "PROTOCOL_VERSION",
    "REQUIRED_MOTION_LIFECYCLE_PHASES",
    "SUPPORTED_UPLINK_TYPES",
    "TERMINAL_MOTION_PHASES",
    "ProtocolError",
    "ack_frame",
    "audio_reply_frame",
    "build_voiceprint_sample_ack",
    "ensure_object",
    "error_frame",
    "hello_ack",
    "motion_failure_event",
    "now_iso",
    "require_type",
    "run_path_dispatch_frame",
    "voice_status_frame",
    "validate_device_info",
    "validate_heartbeat",
    "validate_hello",
    "validate_motion_event",
    "validate_motion_task_lifecycle",
    "validate_self_check",
    "validate_transcript",
    "validate_uplink",
    "validate_voiceprint_sample",
]
