"""Per-message handlers for device gateway WebSocket uplink (CQ-099)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.protocol import ack_frame, hello_ack
from device_gateway.sessions import DeviceSession, registry
from device_gateway.task_events import record_device_connected
from device_gateway.tasks import (
    active_tasks_for_device,
    create_task_from_transcript_async,
    enqueue_pending_task,
)
from device_intelligence.shadow import shadow_store
from routes.device_gateway_dispatch import (
    dispatch_task_to_session,
    drain_pending_tasks,
)
from routes.device_gateway_hello_helpers import (
    _authenticate_hello,
    _check_attestation,
    _create_hello_session,
    _negotiate_hello_protocol,
    _reject_too_many_connections,
)
from routes.device_gateway_ws_motion import handle_motion_event

# P4 瘦身：voice helpers 已删除，voice 相关功能由小智官方云负责
from routes.ws_lifecycle_helpers import reattach_tasks


def handle_audio_chunk(*args, **kwargs):
    """Stub: voice pipeline retired in P4."""
    pass


def handle_voice_transcript(*args, **kwargs):
    """Stub: voice transcript retired in P4."""
    pass


def handle_voiceprint_sample(*args, **kwargs):
    """Stub: voiceprint retired in P4."""
    pass


def _cleanup_audio_registry(*args, **kwargs):
    """Stub: audio registry retired in P4."""
    pass


def _feed_audio_to_pipeline(*args, **kwargs):
    """Stub: audio pipeline retired in P4."""
    pass


from device_gateway.attestation import ACTION_READ_ONLY

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
    # AUDIT-11-W1：连接数达上限，拒绝新设备
    if previous == "too_many":
        await _reject_too_many_connections(websocket, device_id, request_id)
        return None, None, False
    record_device_connected(device_id)
    if isinstance(previous, DeviceSession) and previous.websocket is not websocket:
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
