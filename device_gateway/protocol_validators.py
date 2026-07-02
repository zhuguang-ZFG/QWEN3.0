"""Uplink message validators for the LiMa device protocol."""

from __future__ import annotations

from typing import Any

from device_gateway.protocol import (
    ProtocolError,
    _non_empty_string,
    _optional_request_id,
    ensure_object,
    require_type,
)
from device_gateway.protocol_negotiator import SUPPORTED_PROTOCOLS


def validate_hello(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    protocol = message.get("protocol")
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ProtocolError(
            "E_PROTOCOL_VERSION",
            f"protocol must be one of {', '.join(SUPPORTED_PROTOCOLS)}",
            request_id,
        )
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
        "protocol": protocol,
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
    # Preserve device-reported route_policy_evidence for terminal event tracking (M15)
    route_evidence = message.get("route_policy_evidence")
    if isinstance(route_evidence, dict):
        normalized["route_policy_evidence"] = route_evidence
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


def validate_audio(message: dict[str, Any]) -> dict[str, Any]:
    request_id = _optional_request_id(message)
    device_id = _non_empty_string(message, "device_id")
    data = message.get("data")
    if not isinstance(data, str) or not data.strip():
        raise ProtocolError("E_INVALID_MESSAGE", "audio data must be a non-empty base64 string", request_id)
    seq = message.get("seq", 0)
    if not isinstance(seq, int) or seq < 0:
        seq = 0
    is_end = message.get("is_end", False)
    if not isinstance(is_end, bool):
        is_end = False
    return {
        "type": "audio",
        "device_id": device_id,
        "data": data.strip(),
        "seq": seq,
        "is_end": is_end,
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
        "audio": validate_audio,
    }
    return validators[msg_type](obj)
