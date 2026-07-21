"""Minimal device WS frames for M1 delivery (hello_ack / error / heartbeat_ack)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ProtocolError(Exception):
    def __init__(self, code: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


def error_frame(error: ProtocolError | Exception, request_id: str | None = None) -> dict[str, Any]:
    if isinstance(error, ProtocolError):
        frame: dict[str, Any] = {"type": "error", "code": error.code, "message": error.message}
        req_id = error.request_id or request_id
    else:
        frame = {"type": "error", "code": "E_INTERNAL", "message": "internal device gateway error"}
        req_id = request_id
    frame["request_id"] = req_id
    return frame


def hello_ack(
    device_id: str,
    *,
    protocol_version: str = "lima-device-v1",
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "type": "hello_ack",
        "protocol": protocol_version,
        "device_id": device_id,
        "server_time": now_iso(),
    }
    if capabilities:
        frame["capabilities"] = list(capabilities)
    return frame


def ack_frame(ack_type: str, device_id: str, **extra: Any) -> dict[str, Any]:
    frame = {"type": ack_type, "device_id": device_id, "server_time": now_iso()}
    frame.update(extra)
    return frame
