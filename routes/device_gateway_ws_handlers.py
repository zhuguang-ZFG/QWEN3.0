"""Per-message handlers for device gateway WebSocket uplink (CQ-099)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.protocol import ProtocolError, ack_frame, hello_ack
from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    ack_processing_task,
    create_task_from_transcript,
    enqueue_pending_task,
    record_motion_event,
)
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
        try:
            await previous.websocket.close(code=1012)
        except Exception as exc:
            _log.debug("close superseded websocket device=%s: %s", device_id, type(exc).__name__)
    await session.send_json(hello_ack(device_id))
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
    ack_processing_task(device_id, message["task_id"])
    record_motion_event_observability(message, device_id)
    session = registry.get(device_id)
    if session is not None:
        session.mark_task_acknowledged(message["task_id"])
        await session.send_json(ack_frame("motion_event_ack", device_id, **summary, request_id=request_id))

    # Notify Telegram for significant phase changes
    phase = message.get("phase", "")
    if phase in ("accepted", "running", "done", "failed"):
        try:
            from routes.telegram_cards import send_device_task_card
            import time as _time

            await send_device_task_card(
                task_id=str(message.get("task_id", "")),
                capability=str(message.get("source_capability", message.get("capability", ""))),
                phase=phase,
                progress_pct=int(message.get("progress", {}).get("percent", 0)),
                error_code=str(message.get("error_code", message.get("error", {}).get("code", ""))) if phase == "failed" else "",
                error_message=str(message.get("error_message", message.get("error", {}).get("message", ""))) if phase == "failed" else "",
                device_id=device_id,
            )
        except Exception:
            _log.debug("device task card notification failed", exc_info=True)

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


async def handle_device_info(device_id: str, request_id: str | None) -> None:
    session = registry.get(device_id)
    if session is not None:
        await session.send_json(ack_frame("device_info_ack", device_id, request_id=request_id))


async def handle_self_check(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
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
