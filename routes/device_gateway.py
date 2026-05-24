"""LiMa direct device gateway routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_gateway.auth import token_configured, validate_device_token
from device_gateway.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    ack_frame,
    error_frame,
    hello_ack,
    validate_uplink,
)
from device_gateway.sessions import DeviceSession, registry
from device_gateway.store import configure_task_store_from_env, task_store_health
from device_gateway.notifier import (
    configure_notifier_from_env,
    notifier_health,
    publish_task_available,
    start_task_notifier,
    stop_task_notifier,
)
from device_gateway.tasks import (
    create_task_from_transcript,
    enqueue_pending_task,
    mark_task_dispatched,
    pending_count,
    pop_pending_tasks,
    record_motion_event,
    requeue_pending_tasks,
    reset_tasks_for_tests,
)

router = APIRouter(prefix="/device/v1")


@router.get("/health")
async def device_gateway_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "protocol": PROTOCOL_VERSION,
        "active_sessions": registry.count(),
        "pending_tasks": pending_count(),
        "task_store": task_store_health(),
        "session_bus": notifier_health(),
        "auth_configured": token_configured(),
    }


@router.post("/events", dependencies=[Depends(require_private_api_key)])
async def device_gateway_events(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        message = validate_uplink(body)
    except ProtocolError as exc:
        return JSONResponse(status_code=400, content=error_frame(exc))

    msg_type = message["type"]
    device_id = message.get("device_id", "")
    if msg_type == "motion_event":
        summary = record_motion_event(message)
        return JSONResponse(ack_frame("motion_event_ack", device_id, **summary, request_id=message.get("request_id")))
    if msg_type == "device_info":
        return JSONResponse(ack_frame("device_info_ack", device_id, request_id=message.get("request_id")))
    if msg_type == "self_check":
        return JSONResponse(
            ack_frame("self_check_ack", device_id, status=message.get("status", "unknown"), request_id=message.get("request_id"))
        )
    return JSONResponse(status_code=400, content=error_frame(ProtocolError("E_UNSUPPORTED_TYPE", "event type is not supported", message.get("request_id"))))


@router.post("/tasks", dependencies=[Depends(require_private_api_key)])
async def device_gateway_tasks(request: Request) -> JSONResponse:
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content=error_frame(ProtocolError("E_INVALID_MESSAGE", "message must be a JSON object")))
    device_id = body.get("device_id")
    text = body.get("text")
    request_id = body.get("request_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return JSONResponse(
            status_code=400,
            content=error_frame(ProtocolError("E_INVALID_MESSAGE", "device_id must be a non-empty string", request_id if isinstance(request_id, str) else None)),
        )
    if not isinstance(text, str) or not text.strip():
        return JSONResponse(
            status_code=400,
            content=error_frame(ProtocolError("E_INVALID_MESSAGE", "text must be a non-empty string", request_id if isinstance(request_id, str) else None)),
        )

    task = create_task_from_transcript(device_id.strip(), text.strip(), request_id=request_id if isinstance(request_id, str) else None)
    session = registry.get(device_id.strip())
    sent = False
    if session is not None:
        if await _dispatch_task_to_session(session, task):
            sent = True
            queue_depth = pending_count(device_id.strip())
        else:
            queue_depth = pending_count(device_id.strip())
    else:
        queue_depth = enqueue_pending_task(device_id.strip(), task)
        await publish_task_available(device_id.strip())
    return JSONResponse({"status": "sent" if sent else "queued", "sent": sent, "queue_depth": queue_depth, "task": task})


def _extract_ws_token(websocket: WebSocket) -> str:
    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if authorization.strip():
        return authorization.strip()
    return websocket.query_params.get("token", "").strip()


async def _send_error(websocket: WebSocket, error: ProtocolError | Exception, request_id: str | None = None) -> None:
    await websocket.send_json(error_frame(error, request_id=request_id))


def _requeue_session_outstanding(session: DeviceSession, extra_tasks: list[dict[str, Any]] | None = None) -> int:
    outstanding = session.take_outstanding_tasks()
    tasks = [*outstanding, *(extra_tasks or [])]
    if not tasks:
        return pending_count(session.device_id)
    return requeue_pending_tasks(session.device_id, tasks)


async def _dispatch_task_to_session(session: DeviceSession, task: dict[str, Any]) -> bool:
    try:
        await session.send_json(task)
    except Exception:
        registry.unregister(session.device_id, session.websocket)
        _requeue_session_outstanding(session, [task])
        return False
    session.mark_task_dispatched(task)
    mark_task_dispatched(task["task_id"])
    return True


async def _drain_pending_tasks(session: DeviceSession) -> bool:
    while True:
        pending_tasks = pop_pending_tasks(session.device_id)
        if not pending_tasks:
            return True
        for index, pending_task in enumerate(pending_tasks):
            try:
                await session.send_json(pending_task)
            except Exception:
                registry.unregister(session.device_id, session.websocket)
                _requeue_session_outstanding(session, pending_tasks[index:])
                return False
            session.mark_task_dispatched(pending_task)
            mark_task_dispatched(pending_task["task_id"])


async def _notify_local_session_task_available(device_id: str) -> None:
    session = registry.get(device_id)
    if session is not None:
        await _drain_pending_tasks(session)


async def start_device_gateway_runtime() -> None:
    configure_task_store_from_env()
    configure_notifier_from_env()
    await start_task_notifier(_notify_local_session_task_available)


async def stop_device_gateway_runtime() -> None:
    await stop_task_notifier()


@router.websocket("/ws")
async def device_ws(websocket: WebSocket) -> None:
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
                await _send_error(websocket, exc)
                continue

            msg_type = message["type"]
            request_id = message.get("request_id")

            if msg_type == "hello":
                device_id = message["device_id"]
                if not validate_device_token(device_id, _extract_ws_token(websocket)):
                    await _send_error(
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
                    except Exception:
                        pass
                await session.send_json(hello_ack(device_id))
                if not await _drain_pending_tasks(session):
                    return
                continue

            if not authenticated or not device_id:
                await _send_error(
                    websocket,
                    ProtocolError("E_HELLO_REQUIRED", "hello must be sent before other messages", request_id),
                )
                continue

            if message["device_id"] != device_id:
                await _send_error(
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
                session = registry.get(device_id)
                if session is not None:
                    if not await _dispatch_task_to_session(session, task):
                        return
                else:
                    enqueue_pending_task(device_id, task)
                    return
            elif msg_type == "motion_event":
                summary = record_motion_event(message)
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
                    ack_frame("self_check_ack", device_id, status=message.get("status", "unknown"), request_id=request_id)
                )
    except WebSocketDisconnect:
        pass
    finally:
        if session is not None:
            _requeue_session_outstanding(session)
        if device_id:
            registry.unregister(device_id, websocket)


def _reset_for_tests() -> None:
    registry.clear()
    reset_tasks_for_tests()
