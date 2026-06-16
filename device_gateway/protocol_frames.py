"""Downlink frame builders for the LiMa device protocol."""

from __future__ import annotations

from typing import Any

from device_gateway.protocol_core import PROTOCOL_VERSION, ProtocolError, now_iso
from device_gateway.protocol_families import MotionErrorCode


def error_frame(error: ProtocolError | Exception, request_id: str | None = None) -> dict[str, Any]:
    if isinstance(error, ProtocolError):
        frame = {"type": "error", "code": error.code, "message": error.message}
        req_id = error.request_id or request_id
    else:
        frame = {"type": "error", "code": "E_INTERNAL", "message": "internal device gateway error"}
        req_id = request_id
    if req_id:
        frame["request_id"] = req_id
    return frame


def hello_ack(device_id: str, shadow_delta: dict[str, Any] | None = None) -> dict[str, Any]:
    frame = {
        "type": "hello_ack",
        "protocol": PROTOCOL_VERSION,
        "device_id": device_id,
        "server_time": now_iso(),
    }
    if shadow_delta:
        frame.update(shadow_delta)
    return frame


def build_voiceprint_sample_ack(device_id: str, voiceprint_id: str, sample_index: int, **extra: Any) -> dict[str, Any]:
    return {
        "type": "voiceprint_sample_ack",
        "device_id": device_id,
        "voiceprint_id": voiceprint_id,
        "sample_index": sample_index,
        "server_time": now_iso(),
        **extra,
    }


def ack_frame(ack_type: str, device_id: str, **extra: Any) -> dict[str, Any]:
    frame = {"type": ack_type, "device_id": device_id, "server_time": now_iso()}
    frame.update(extra)
    return frame


def run_path_dispatch_frame(
    device_id: str,
    task_id: str,
    path: list[dict[str, float]],
    feed: float = 500.0,
    request_id: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a downlink dispatch frame for a run_path motion task.

    The 'path' parameter is a list of {x, y, z} dictionaries representing
    the absolute toolpath in millimetres. The 'feed' parameter is the
    feed rate in mm/min. The device must execute the path and report
    progress via motion_event uplinks.
    """
    frame: dict[str, Any] = {
        "type": "task_dispatch",
        "device_id": device_id,
        "task_id": task_id,
        "capability": "run_path",
        "params": {
            "path": path,
            "feed": float(feed),
        },
    }
    if request_id:
        frame["request_id"] = request_id
    if extra_params:
        for key in ("source_capability", "text", "prompt", "preview_svg"):
            if key in extra_params:
                frame["params"][key] = extra_params[key]
    return frame


def motion_failure_event(
    device_id: str,
    task_id: str,
    error_code: MotionErrorCode,
    reason: str = "",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a standards-compliant motion failure event frame."""
    frame: dict[str, Any] = {
        "type": "motion_event",
        "device_id": device_id,
        "task_id": task_id,
        "phase": "failed",
        "error": {"code": error_code.value, "reason": reason or error_code.value},
    }
    if request_id:
        frame["request_id"] = request_id
    return frame
