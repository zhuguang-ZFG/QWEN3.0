"""Hello handshake mechanics for device gateway WebSocket uplink (U batch).

Extracted from routes/device_gateway_ws_handlers.py so the per-message dispatcher
owns only the public handlers (handle_hello/heartbeat/transcript/...), while this
module owns the hello handshake sub-domain: device auth, protocol negotiation,
session creation, firmware attestation, and connection-limit rejection.

handle_hello stays in ws_handlers as the public entry point and delegates to
these private helpers.

attestation_verifier is a stable module-level singleton (no
set_*_for_tests / install_*_for_tests swap interface — verified by ripgrep),
so a top-level import is safe here, mirroring the stable-singleton pattern in
device_gateway_events_routes (S batch lesson). conftest.py and
test_device_attestation.py patch attestation_verifier via THIS module's
attribute (repointed from ws_handlers during extraction); they replace the
module attribute with an isolated verifier, so _check_attestation must look it
up here, not in ws_handlers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.attestation import AttestationResult, verifier as attestation_verifier
from device_gateway.auth import validate_device_token
from device_gateway.protocol import (
    ProtocolError,
    attestation_failed_frame,
    attestation_warning_frame,
)
from device_gateway.protocol_negotiator import ProtocolNegotiator
from device_gateway.sessions import DeviceSession
from routes.device_gateway_dispatch import (
    extract_ws_token,
    send_ws_error,
    ticket_device_id,
)

_log = logging.getLogger(__name__)


async def _authenticate_hello(
    websocket: WebSocket,
    device_id: str,
    request_id: str | None,
) -> bool:
    """Validate device ticket and token; send error and close on failure."""
    bound_device_id = ticket_device_id(websocket)
    if bound_device_id and bound_device_id != device_id:
        _log.warning("device hello ticket device mismatch expected=%r got=%r", bound_device_id, device_id)
        await send_ws_error(
            websocket,
            ProtocolError("E_UNAUTHORIZED_DEVICE", "device ticket does not match device_id", request_id),
        )
        await websocket.close(code=1008)
        return False
    token = extract_ws_token(websocket)
    if not validate_device_token(device_id, token):
        _log.warning("device hello auth failed device=%r token_len=%d", device_id, len(token))
        await send_ws_error(
            websocket,
            ProtocolError("E_UNAUTHORIZED_DEVICE", "device token is invalid", request_id),
        )
        await websocket.close(code=1008)
        return False
    return True


def _negotiate_hello_protocol(message: dict[str, Any]) -> tuple[str, frozenset[str]]:
    """Negotiate protocol version and return (protocol, capabilities)."""
    fw_rev = message.get("fw_rev", "")
    device_protocol = message.get("protocol", "lima-device-v1")
    negotiator = ProtocolNegotiator()
    protocol = negotiator.negotiate(device_protocol, fw_rev)
    return protocol, negotiator.capabilities_for_version(protocol)


def _create_hello_session(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    protocol: str,
    capabilities: frozenset[str],
    attestation_action: str,
) -> DeviceSession:
    return DeviceSession(
        device_id=device_id,
        websocket=websocket,
        fw_rev=message.get("fw_rev", ""),
        capabilities=message.get("capabilities", []),
        protocol_version=protocol,
        negotiated_capabilities=capabilities,
        attestation_action=attestation_action,
    )


async def _check_attestation(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> AttestationResult | None:
    """Verify firmware attestation; send frame and return None on quarantine."""
    version = message.get("firmwareVersion") or message.get("fw_rev", "")
    firmware_hash = message.get("firmwareHash", "")
    result = attestation_verifier.verify(device_id, firmware_hash, version)
    if result.action == "quarantine":
        _log.warning(
            "device attestation quarantined device=%s version=%r reason=%s", device_id, result.version, result.reason
        )
        await websocket.send_json(attestation_failed_frame(device_id, result.reason, request_id))
        await websocket.close(code=1008)
        return None
    if result.action == "read_only":
        _log.warning(
            "device attestation warning device=%s version=%r reason=%s", device_id, result.version, result.reason
        )
        await websocket.send_json(attestation_warning_frame(device_id, result.reason, request_id))
    return result


async def _reject_too_many_connections(websocket: WebSocket, device_id: str, request_id: str | None) -> None:
    """AUDIT-11-W1：连接数达上限时拒绝新设备。"""
    _log.warning("device connection limit reached, rejecting device=%s", device_id)
    await send_ws_error(
        websocket,
        ProtocolError("E_TOO_MANY_CONNECTIONS", "server connection limit reached", request_id),
    )
    await websocket.close(code=1013)
