"""Protocol helpers for LiMa direct device sessions.

This module is a compatibility facade over the split protocol package:
- protocol_core: constants, ProtocolError, and low-level helpers
- protocol_validators: uplink message validators
- protocol_frames: downlink frame builders
- protocol_lifecycle (merged): motion task lifecycle validation
"""

from __future__ import annotations

from typing import Any

from device_gateway.protocol_core import (
    PROTOCOL_VERSION,
    REQUIRED_MOTION_LIFECYCLE_PHASES,
    SUPPORTED_UPLINK_TYPES,
    TERMINAL_MOTION_PHASES,
    ProtocolError,
    ensure_object,
    now_iso,
    require_type,
)
from device_gateway.protocol_frames import (
    ack_frame,
    audio_reply_frame,
    build_voiceprint_sample_ack,
    error_frame,
    hello_ack,
    motion_failure_event,
    run_path_dispatch_frame,
    voice_status_frame,
)
from device_gateway.protocol_validators import (
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
