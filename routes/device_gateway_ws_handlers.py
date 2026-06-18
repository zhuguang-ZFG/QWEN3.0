"""Per-message handlers for device gateway WebSocket uplink (CQ-099)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.protocol import (
    ProtocolError,
    ack_frame,
    hello_ack,
    voice_status_frame,
)
from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    ack_processing_task,
    active_tasks_for_device,
    create_task_from_transcript_async,
    enqueue_pending_task,
    execute_recovery,
    mark_task_dispatched,
    record_motion_event,
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
)
from routes.device_voice_ws_helpers import (
    _cleanup_audio_registry,
    _feed_audio_to_pipeline,
    handle_audio_chunk,
)
from routes.ws_lifecycle_helpers import reattach_tasks
from routes.ws_task_helpers import record_outcome_ledger, send_recovery_ack
from routes.ws_voice_transcript_helpers import handle_voice_transcript
from routes.ws_voiceprint_helpers import handle_voiceprint_sample
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


async def handle_hello(
    websocket: WebSocket,
    message: dict[str, Any],
    *,
    request_id: str | None,
) -> tuple[str | None, DeviceSession | None, bool]:
    device_id = message["device_id"]
    if not validate_device_token(device_id, extract_ws_token(websocket)):
        await send_ws_error(
            websocket,
            ProtocolError("E_UNAUTHORIZED_DEVICE", "device token is invalid", request_id),
        )
        await websocket.close(code=1008)
        return None, None, False

    session = DeviceSession(
        device_id=device_id,
        websocket=websocket,
        fw_rev=message.get("fw_rev", ""),
        capabilities=message.get("capabilities", []),
    )
    previous = registry.register(session)
    if previous and previous.websocket is not websocket:
        reattach_tasks(session, previous.take_outstanding_tasks())
        try:
            await previous.websocket.close(code=1012)
        except Exception as exc:
            _log.debug("close superseded websocket device=%s: %s", device_id, type(exc).__name__)
    reattach_tasks(session, active_tasks_for_device(device_id))
    shadow_store.update_hello(message)
    await session.send_json(hello_ack(device_id, shadow_store.delta_for_hello(device_id)))
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

    task = await create_task_from_transcript_async(device_id, message["text"], request_id=request_id)
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


async def handle_motion_event(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    summary = record_motion_event(message)
    shadow_store.update_motion_event(message)
    ack_processing_task(device_id, message["task_id"])
    record_motion_event_observability(message, device_id)

    # M5: execute recovery action on failure
    recovery_result = execute_recovery(message.get("task_id", ""), device_id, message)
    if recovery_result:
        _log.info(
            "device recovery action=%s attempt=%s device_id=%s task_id=%s",
            recovery_result["action"],
            recovery_result.get("attempt", 0),
            device_id,
            message.get("task_id", ""),
        )
        session = registry.get(device_id)
        if session is not None:
            await send_recovery_ack(session, device_id, message, request_id, recovery_result)

    session = registry.get(device_id)
    if session is not None:
        session.mark_task_acknowledged(message["task_id"])
        await session.send_json(ack_frame("motion_event_ack", device_id, **summary, request_id=request_id))

    phase = message.get("phase", "")
    if phase in ("accepted", "running", "done", "failed"):
        _log.info(
            "device task phase device_id=%s task_id=%s phase=%s",
            device_id,
            message.get("task_id", ""),
            phase,
        )

    # Record to Outcome Ledger (terminal phases only)
    if phase in ("done", "failed", "cancelled"):
        record_outcome_ledger(device_id, message, phase)


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
