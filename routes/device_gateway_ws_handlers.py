"""Per-message handlers for device gateway WebSocket uplink (CQ-099)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.protocol import (
    ProtocolError,
    ack_frame,
    attestation_failed_frame,
    attestation_warning_frame,
    hello_ack,
    voice_status_frame,
)
from device_gateway.protocol_negotiator import ProtocolNegotiator
from device_gateway.sessions import DeviceSession, registry
from device_gateway.task_events import record_device_connected
from device_gateway.tasks import (
    ack_processing_task,
    active_tasks_for_device,
    create_task_from_transcript_async,
    enqueue_pending_task,
    mark_task_dispatched,
    remove_pending_task,
)
from device_intelligence.shadow import shadow_store
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError
from routes.device_gateway_dispatch import (
    dispatch_task_to_session,
    drain_pending_tasks,
    extract_ws_token,
    record_motion_event_observability,
    send_ws_error,
    ticket_device_id,
)
from routes.device_gateway_ws_motion import handle_motion_event
from routes.device_voice_ws_helpers import (
    _cleanup_audio_registry,
    _feed_audio_to_pipeline,
    handle_audio_chunk,
)
from routes.ws_lifecycle_helpers import reattach_tasks
from routes.ws_voice_transcript_helpers import handle_voice_transcript
from routes.ws_voiceprint_helpers import handle_voiceprint_sample
from device_gateway.attestation import ACTION_READ_ONLY, AttestationResult, verifier as attestation_verifier
from device_gateway.auth import validate_device_token

_log = logging.getLogger(__name__)

__all__ = [
    "handle_hello",
    "handle_heartbeat",
    "handle_transcript",
    "handle_motion_event",
    "handle_device_info",
    "handle_self_check",
    "handle_voiceprint_sample",
    "handle_audio_chunk",
    "_feed_audio_to_pipeline",
    "_cleanup_audio_registry",
]


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


async def handle_hello(
    websocket: WebSocket,
    message: dict[str, Any],
    *,
    request_id: str | None,
) -> tuple[str | None, DeviceSession | None, bool]:
    device_id = message["device_id"]
    if not await _authenticate_hello(websocket, device_id, request_id):
        return None, None, False
    _log.info("device hello auth succeeded device=%r", device_id)

    attestation = await _check_attestation(websocket, device_id, message, request_id)
    if attestation is None:
        return None, None, False

    protocol, negotiated_capabilities = _negotiate_hello_protocol(message)
    session = _create_hello_session(
        websocket, device_id, message, protocol, negotiated_capabilities, attestation.action
    )

    previous = registry.register(session)
    record_device_connected(device_id)
    if previous and previous.websocket is not websocket:
        reattach_tasks(session, previous.take_outstanding_tasks())
        try:
            await previous.websocket.close(code=1012)
        except Exception as exc:
            _log.warning("close superseded websocket device=%s: %s", device_id, exc)
    reattach_tasks(session, active_tasks_for_device(device_id))
    shadow_store.update_hello(message)
    await session.send_json(
        hello_ack(
            device_id,
            shadow_store.delta_for_hello(device_id),
            protocol_version=protocol,
            capabilities=negotiated_capabilities,
        )
    )
    if attestation.action == ACTION_READ_ONLY:
        # Read-only sessions stay connected but do not receive queued tasks.
        return device_id, session, True
    if not await drain_pending_tasks(session):
        return device_id, session, False
    return device_id, session, True


async def handle_heartbeat(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> None:
    registry.update_heartbeat(device_id, message["uptime_ms"])
    shadow_store.update_heartbeat(device_id, message["uptime_ms"])
    session = registry.get(device_id)
    sender = session.send_json if session is not None else websocket.send_json
    await sender(
        ack_frame(
            "heartbeat_ack",
            device_id,
            uptime_ms=message["uptime_ms"],
            request_id=request_id,
        )
    )


async def handle_transcript(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> bool:
    session = registry.get(device_id)
    if session is not None and "text_chat" in session.capabilities:
        return await handle_voice_transcript(session, device_id, message.get("text", ""), request_id)

    task = await create_task_from_transcript_async(
        device_id, message["text"], request_id=request_id, entrypoint="ws_transcript"
    )
    if task.get("error"):
        await websocket.send_json(
            ack_frame(
                "motion_task_failed",
                device_id,
                task_id=task["task_id"],
                error=task["error"],
                request_id=request_id,
            )
        )
        return True
    if session is not None:
        return await dispatch_task_to_session(session, task)
    enqueue_pending_task(device_id, task)
    return False


async def handle_device_info(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    shadow_store.update_device_info(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(ack_frame("device_info_ack", device_id, request_id=request_id))


async def handle_self_check(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    shadow_store.update_self_check(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(
            ack_frame(
                "self_check_ack",
                device_id,
                status=message.get("status", "unknown"),
                request_id=request_id,
            )
        )
