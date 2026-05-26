"""Device gateway WebSocket uplink loop (CQ-096)."""

from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

from device_gateway.auth import validate_device_token
from device_gateway.protocol import ProtocolError, ack_frame, hello_ack, validate_uplink
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
    requeue_session_outstanding,
    send_ws_error,
)

_log = logging.getLogger(__name__)


async def handle_device_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    device_id: str | None = None
    session: DeviceSession | None = None
    authenticated = False
    try:
        while True:
            raw = await websocket.receive_json()
            try:
                message = validate_uplink(raw)
            except ProtocolError as exc:
                await send_ws_error(websocket, exc)
                continue

            msg_type = message["type"]
            request_id = message.get("request_id")

            if msg_type == "hello":
                device_id = message["device_id"]
                if not validate_device_token(device_id, extract_ws_token(websocket)):
                    await send_ws_error(
                        websocket,
                        ProtocolError("E_UNAUTHORIZED_DEVICE", "device token is invalid", request_id),
                    )
                    await websocket.close(code=1008)
                    return
                authenticated = True
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
                        _log.debug(
                            "close superseded websocket device=%s: %s",
                            device_id,
                            type(exc).__name__,
                        )
                await session.send_json(hello_ack(device_id))
                if not await drain_pending_tasks(session):
                    return
                continue

            if not authenticated or not device_id:
                await send_ws_error(
                    websocket,
                    ProtocolError("E_HELLO_REQUIRED", "hello must be sent before other messages", request_id),
                )
                continue

            if message["device_id"] != device_id:
                await send_ws_error(
                    websocket,
                    ProtocolError("E_DEVICE_MISMATCH", "message device_id does not match session", request_id),
                )
                continue

            if msg_type == "heartbeat":
                registry.update_heartbeat(device_id, message["uptime_ms"])
                session = registry.get(device_id)
                sender = session.send_json if session is not None else websocket.send_json
                await sender(
                    ack_frame("heartbeat_ack", device_id, uptime_ms=message["uptime_ms"], request_id=request_id)
                )
            elif msg_type == "transcript":
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
                    continue
                session = registry.get(device_id)
                if session is not None:
                    if not await dispatch_task_to_session(session, task):
                        return
                else:
                    enqueue_pending_task(device_id, task)
                    return
            elif msg_type == "motion_event":
                summary = record_motion_event(message)
                ack_processing_task(device_id, message["task_id"])
                record_motion_event_observability(message, device_id)
                session = registry.get(device_id)
                if session is not None:
                    session.mark_task_acknowledged(message["task_id"])
                sender = session.send_json if session is not None else websocket.send_json
                await sender(ack_frame("motion_event_ack", device_id, **summary, request_id=request_id))
            elif msg_type == "device_info":
                session = registry.get(device_id)
                sender = session.send_json if session is not None else websocket.send_json
                await sender(ack_frame("device_info_ack", device_id, request_id=request_id))
            elif msg_type == "self_check":
                session = registry.get(device_id)
                sender = session.send_json if session is not None else websocket.send_json
                await sender(
                    ack_frame(
                        "self_check_ack",
                        device_id,
                        status=message.get("status", "unknown"),
                        request_id=request_id,
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        if session is not None:
            requeue_session_outstanding(session)
        if device_id:
            registry.unregister(device_id, websocket)
