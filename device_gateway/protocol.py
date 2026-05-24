"""Protocol helpers for LiMa direct device sessions."""
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
}


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
    return {
        "type": "motion_event",
        "device_id": device_id,
        "session_id": message.get("session_id"),
        "task_id": task_id,
        "phase": phase,
        "progress": progress,
        "request_id": request_id,
    }


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


def hello_ack(device_id: str) -> dict[str, Any]:
    return {
        "type": "hello_ack",
        "protocol": PROTOCOL_VERSION,
        "device_id": device_id,
        "server_time": now_iso(),
    }


def ack_frame(ack_type: str, device_id: str, **extra: Any) -> dict[str, Any]:
    frame = {"type": ack_type, "device_id": device_id, "server_time": now_iso()}
    frame.update(extra)
    return frame
