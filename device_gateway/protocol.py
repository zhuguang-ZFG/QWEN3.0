"""Protocol helpers for LiMa direct device sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from device_gateway.protocol_families import MotionErrorCode

PROTOCOL_VERSION = "lima-device-v1"
SUPPORTED_UPLINK_TYPES = {
    "hello",
    "heartbeat",
    "transcript",
    "motion_event",
    "device_info",
    "self_check",
    "voiceprint_sample",
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


def validate_hello(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    protocol = message.get("protocol")
    if protocol != PROTOCOL_VERSION:
        raise ProtocolError("E_PROTOCOL_VERSION", "protocol must be lima-device-v1", request_id)
    device_id = _non_empty_string(message, "device_id")
    capabilities = message.get("capabilities", [])
    if capabilities is None:
        capabilities = []
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        raise ProtocolError("E_INVALID_MESSAGE", "capabilities must be a list of strings", request_id)
    fw_rev = message.get("fw_rev", "")
    if fw_rev is None:
        fw_rev = ""
    if not isinstance(fw_rev, str):
        raise ProtocolError("E_INVALID_MESSAGE", "fw_rev must be a string", request_id)
    return {
        "type": "hello",
        "protocol": PROTOCOL_VERSION,
        "device_id": device_id,
        "fw_rev": fw_rev,
        "capabilities": capabilities,
        "request_id": request_id,
        "model": message.get("model", ""),
        "hw_rev": message.get("hw_rev", ""),
        "workspace_mm": message.get("workspace_mm", {}),
        "profile_id": message.get("profile_id", ""),
    }


def validate_heartbeat(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    device_id = _non_empty_string(message, "device_id")
    uptime_ms = message.get("uptime_ms", 0)
    if not isinstance(uptime_ms, int) or uptime_ms < 0:
        raise ProtocolError("E_INVALID_MESSAGE", "uptime_ms must be a non-negative integer", request_id)
    return {"type": "heartbeat", "device_id": device_id, "uptime_ms": uptime_ms, "request_id": request_id}


def validate_transcript(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    device_id = _non_empty_string(message, "device_id")
    text = _non_empty_string(message, "text")[:500]
    return {"type": "transcript", "device_id": device_id, "text": text, "request_id": request_id}


def validate_motion_event(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    device_id = message.get("device_id")
    if device_id is None:
        device_id = message.get("session_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ProtocolError("E_INVALID_MESSAGE", "device_id must be a non-empty string", request_id)
    device_id = device_id.strip()
    task_id = _non_empty_string(message, "task_id")
    phase = _non_empty_string(message, "phase")
    allowed = {"accepted", "queued", "running", "progress", "done", "failed", "cancelled", "rejected", "stopped"}
    if phase not in allowed:
        raise ProtocolError("E_INVALID_MESSAGE", "phase is not supported", request_id)
    progress = message.get("progress", {})
    if progress is None:
        progress = {}
    if not isinstance(progress, dict):
        raise ProtocolError("E_INVALID_MESSAGE", "progress must be an object", request_id)
    normalized = {
        "type": "motion_event",
        "device_id": device_id,
        "session_id": message.get("session_id"),
        "task_id": task_id,
        "phase": phase,
        "progress": progress,
        "request_id": request_id,
    }
    error = _motion_event_error(message)
    if error:
        normalized["error"] = error
    return normalized


def validate_device_info(message: dict[str, Any]) -> dict[str, Any]:
    normalized = {"type": "device_info", "device_id": _non_empty_string(message, "device_id")}
    for key in ("model", "hw_rev", "fw_rev", "workspace_mm"):
        if key in message:
            normalized[key] = message[key]
    request_id = _optional_request_id(message)
    if request_id:
        normalized["request_id"] = request_id
    return normalized


def validate_self_check(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    checks = message.get("checks", [])
    if checks is None:
        checks = []
    if not isinstance(checks, list):
        raise ProtocolError("E_INVALID_MESSAGE", "checks must be a list", request_id)
    return {
        "type": "self_check",
        "device_id": _non_empty_string(message, "device_id"),
        "status": message.get("status", "unknown"),
        "checks": checks,
        "request_id": request_id,
    }


def validate_voiceprint_sample(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    device_id = _non_empty_string(message, "device_id")
    voiceprint_id = _non_empty_string(message, "voiceprint_id")
    sample_index = message.get("sample_index", 0)
    if not isinstance(sample_index, int) or sample_index < 0:
        raise ProtocolError("E_INVALID_MESSAGE", "sample_index must be a non-negative integer", request_id)
    audio_data = message.get("audio_data")
    if not isinstance(audio_data, str) or not audio_data.strip():
        raise ProtocolError("E_INVALID_MESSAGE", "audio_data must be a non-empty string", request_id)
    format = message.get("format", "raw_pcm")
    if format not in ("raw_pcm", "wav", "opus", "g711", "pcm"):
        raise ProtocolError("E_INVALID_MESSAGE", "format must be one of raw_pcm, wav, opus, g711, or pcm", request_id)
    return {
        "type": "voiceprint_sample",
        "device_id": device_id,
        "voiceprint_id": voiceprint_id,
        "sample_index": sample_index,
        "audio_data": audio_data.strip(),
        "format": format,
        "request_id": request_id,
    }


def validate_uplink(message: Any) -> dict[str, Any]:
    obj = ensure_object(message)
    msg_type = require_type(obj)
    validators = {
        "hello": validate_hello,
        "heartbeat": validate_heartbeat,
        "transcript": validate_transcript,
        "motion_event": validate_motion_event,
        "device_info": validate_device_info,
        "self_check": validate_self_check,
        "voiceprint_sample": validate_voiceprint_sample,
    }
    return validators[msg_type](obj)


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


def _motion_event_error(message: dict[str, Any]) -> dict[str, str] | None:
    raw_error = message.get("error")
    if isinstance(raw_error, dict):
        code = raw_error.get("code")
        reason = raw_error.get("reason")
        if isinstance(code, str) and code.strip():
            return {
                "code": code.strip()[:80],
                "reason": str(reason or code).strip()[:240],
            }
    code = message.get("error_code")
    if isinstance(code, str) and code.strip():
        reason = message.get("error_message")
        return {
            "code": code.strip()[:80],
            "reason": str(reason or code).strip()[:240],
        }
    return None


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
