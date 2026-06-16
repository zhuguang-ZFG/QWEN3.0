"""Protocol helpers for LiMa direct device sessions.

This module is a compatibility facade over the split protocol package:
- protocol_core: constants, ProtocolError, and low-level helpers
- protocol_validators: uplink message validators
- protocol_frames: downlink frame builders
- protocol_lifecycle: motion task lifecycle validation
"""

from __future__ import annotations

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
    build_voiceprint_sample_ack,
    error_frame,
    hello_ack,
    motion_failure_event,
    run_path_dispatch_frame,
)
from device_gateway.protocol_lifecycle import validate_motion_task_lifecycle
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
    "build_voiceprint_sample_ack",
    "ensure_object",
    "error_frame",
    "hello_ack",
    "motion_failure_event",
    "now_iso",
    "require_type",
    "run_path_dispatch_frame",
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
