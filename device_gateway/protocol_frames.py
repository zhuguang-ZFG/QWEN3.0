"""Downlink frame builders for the LiMa device protocol."""

from __future__ import annotations

from typing import Any

from device_gateway.protocol import PROTOCOL_VERSION, ProtocolError, now_iso
from device_gateway.protocol_families import MotionErrorCode


def error_frame(error: ProtocolError | Exception, request_id: str | None = None) -> dict[str, Any]:
    if isinstance(error, ProtocolError):
        frame: dict[str, Any] = {"type": "error", "code": error.code, "message": error.message}
        req_id = error.request_id or request_id
    else:
        frame = {"type": "error", "code": "E_INTERNAL", "message": "internal device gateway error"}
        req_id = request_id
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


def voice_status_frame(
    device_id: str,
    status: str,
    *,
    transcript: str = "",
    request_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a voice_status downlink frame for VAD/ASR progress updates.

    status values: 'listening', 'transcribing', 'thinking', 'speaking', 'idle'
    """
    frame: dict[str, Any] = {
        "type": "voice_status",
        "device_id": device_id,
        "status": status,
        "server_time": now_iso(),
    }
    if transcript:
        frame["transcript"] = transcript
    if request_id:
        frame["request_id"] = request_id
    frame.update(extra)
    return frame


def audio_reply_frame(
    device_id: str,
    audio_format: str = "pcm",
    sample_rate: int = 16000,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a metadata frame that precedes binary audio reply.

    Sent as JSON before the binary PCM frame so the device knows
    the audio format and can prepare its playback pipeline.
    """
    frame: dict[str, Any] = {
        "type": "audio_reply",
        "device_id": device_id,
        "format": audio_format,
        "sample_rate": sample_rate,
        "channels": 1,
        "sample_width": 2,
        "server_time": now_iso(),
    }
    if request_id:
        frame["request_id"] = request_id
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
