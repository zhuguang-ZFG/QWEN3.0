"""Per-message handlers for device gateway WebSocket uplink (CQ-099)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_intelligence.shadow import shadow_store
from device_gateway.protocol import ProtocolError, ack_frame, build_voiceprint_sample_ack, hello_ack
from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    ack_processing_task,
    active_tasks_for_device,
    create_task_from_transcript,
    enqueue_pending_task,
    record_motion_event,
)
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
from device_gateway.auth import validate_device_token

_log = logging.getLogger(__name__)


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
        _reattach_tasks(session, previous.take_outstanding_tasks())
        try:
            await previous.websocket.close(code=1012)
        except Exception as exc:
            _log.debug("close superseded websocket device=%s: %s", device_id, type(exc).__name__)
    _reattach_tasks(session, active_tasks_for_device(device_id))
    shadow_store.update_hello(message)
    await session.send_json(hello_ack(device_id, shadow_store.delta_for_hello(device_id)))
    if not await drain_pending_tasks(session):
        return device_id, session, False
    return device_id, session, True


def _reattach_tasks(session: DeviceSession, tasks: list[dict[str, Any]]) -> None:
    seen = set(session.inflight_tasks)
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id or task_id in seen:
            continue
        session.mark_task_dispatched(task)
        seen.add(task_id)
        _record_device_reconnected(session.device_id, task_id)
        _recover_workflow(task_id)


def _record_device_reconnected(device_id: str, task_id: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=task_id,
            device_id=device_id,
            payload={
                "motion_event": {
                    "type": "motion_event",
                    "device_id": device_id,
                    "task_id": task_id,
                    "phase": "device_reconnected",
                }
            },
        )
    )


def _recover_workflow(task_id: str) -> None:
    try:
        current = workflow.get_state(task_id)
        if current == TaskState.DISPATCHED:
            workflow.advance(task_id, TaskState.RUNNING)
            current = TaskState.RUNNING
        if current == TaskState.RUNNING:
            workflow.advance(task_id, TaskState.RECOVERING)
            workflow.advance(task_id, TaskState.RUNNING)
    except WorkflowTransitionError as exc:
        _log.debug("workflow reconnect recovery skipped task=%s err=%s", task_id, exc)


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
    task = create_task_from_transcript(device_id, message["text"], request_id=request_id)
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
    session = registry.get(device_id)
    if session is not None:
        return await dispatch_task_to_session(session, task)
    enqueue_pending_task(device_id, task)
    return False


async def handle_motion_event(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    summary = record_motion_event(message)
    shadow_store.update_motion_event(message)
    ack_processing_task(device_id, message["task_id"])
    record_motion_event_observability(message, device_id)
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
        try:
            from session_memory.outcome_ledger import record as ledger_record

            ledger_record(
                source="device_gateway",
                event_type="device_task",
                outcome="success" if phase == "done" else "failure",
                task_id=str(message.get("task_id", "")),
                scenario="device",
                summary=f"{phase}: {message.get('capability', message.get('source_capability', ''))}",
                tags=["device", phase, str(message.get("capability", ""))],
            )
        except Exception:
            _log.debug("outcome ledger record failed", exc_info=True)


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


async def handle_voiceprint_sample(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> None:
    validated = shadow_store.validate_voiceprint_sample(message)
    member_id = validated.get("member_id")
    voiceprint_id = validated.get("voiceprint_id")
    sample_index = validated.get("sample_index", 0)

    try:
        from session_memory.store_db import upsert_voiceprint_sample

        upsert_voiceprint_sample(
            voiceprint_id=voiceprint_id,
            member_id=member_id,
            device_id=device_id,
            sample_index=sample_index,
            audio_data=validated.get("audio_data"),
            format=validated.get("format", "raw_pcm"),
        )

        ack = build_voiceprint_sample_ack(
            device_id=device_id,
            voiceprint_id=voiceprint_id,
            sample_index=sample_index,
            request_id=request_id,
        )
        await websocket.send_json(ack)
    except ImportError:
        _log.debug("session_memory.store_db not installed; skipping voiceprint sample validation")
        await websocket.send_json(
            ack_frame(
                "voiceprint_sample_ack",
                device_id,
                voiceprint_id=voiceprint_id,
                sample_index=sample_index,
                request_id=request_id,
            )
        )
        return

    shadow_store.update_voiceprint_sample(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(
            ack_frame(
                "voiceprint_sample_ack",
                device_id,
                voiceprint_id=voiceprint_id,
                sample_index=sample_index,
                request_id=request_id,
            )
        )


async def handle_voiceprint_sample(
    websocket: WebSocket,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
) -> None:
    validated = shadow_store.validate_voiceprint_sample(message)
    member_id = validated.get("member_id")
    voiceprint_id = validated.get("voiceprint_id")
    sample_index = validated.get("sample_index", 0)

    try:
        from session_memory.store_db import upsert_voiceprint_sample

        upsert_voiceprint_sample(
            voiceprint_id=voiceprint_id,
            member_id=member_id,
            device_id=device_id,
            sample_index=sample_index,
            audio_data=validated.get("audio_data"),
            format=validated.get("format", "raw_pcm"),
        )

        ack = build_voiceprint_sample_ack(
            device_id=device_id,
            voiceprint_id=voiceprint_id,
            sample_index=sample_index,
            request_id=request_id,
        )
        await websocket.send_json(ack)
    except ImportError:
        _log.debug("session_memory.store_db not installed; skipping voiceprint sample validation")
        await websocket.send_json(
            ack_frame(
                "voiceprint_sample_ack",
                device_id,
                voiceprint_id=voiceprint_id,
                sample_index=sample_index,
                request_id=request_id,
            )
        )
        return

    shadow_store.update_voiceprint_sample(message)
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(
            ack_frame(
                "voiceprint_sample_ack",
                device_id,
                voiceprint_id=voiceprint_id,
                sample_index=sample_index,
                request_id=request_id,
            )
        )
