"""LiMa direct device gateway HTTP routes."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_gateway.auth import token_configured
from device_gateway.notifier import (
    configure_notifier_from_env,
    notifier_health,
    publish_task_available,
    start_task_notifier,
    stop_task_notifier,
)
from device_gateway.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    ack_frame,
    error_frame,
    validate_uplink,
)
from device_gateway.sessions import registry
from device_gateway.store import configure_task_store_from_env, task_store_health
from device_gateway.tasks import (
    ack_processing_task,
    create_task_from_transcript,
    enqueue_pending_task,
    pending_count,
    record_motion_event,
    reset_tasks_for_tests,
)
from routes.device_gateway_dispatch import (
    dispatch_task_to_session,
    drain_pending_tasks,
    notify_local_session_task_available,
    record_motion_event_observability,
)
from routes.device_gateway_ws import handle_device_ws

router = APIRouter(prefix="/device/v1")

# Back-compat for tests
_dispatch_task_to_session = dispatch_task_to_session
_drain_pending_tasks = drain_pending_tasks
_notify_local_session_task_available = notify_local_session_task_available


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
        ack_processing_task(device_id, message["task_id"])
        record_motion_event_observability(message, device_id)
        return JSONResponse(
            ack_frame("motion_event_ack", device_id, **summary, request_id=message.get("request_id"))
        )
    if msg_type == "device_info":
        return JSONResponse(ack_frame("device_info_ack", device_id, request_id=message.get("request_id")))
    if msg_type == "self_check":
        return JSONResponse(
            ack_frame(
                "self_check_ack",
                device_id,
                status=message.get("status", "unknown"),
                request_id=message.get("request_id"),
            )
        )
    return JSONResponse(
        status_code=400,
        content=error_frame(
            ProtocolError("E_UNSUPPORTED_TYPE", "event type is not supported", message.get("request_id"))
        ),
    )


@router.post("/tasks", dependencies=[Depends(require_private_api_key)])
async def device_gateway_tasks(request: Request) -> JSONResponse:
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400,
            content=error_frame(ProtocolError("E_INVALID_MESSAGE", "message must be a JSON object")),
        )
    device_id = body.get("device_id")
    text = body.get("text")
    request_id = body.get("request_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return JSONResponse(
            status_code=400,
            content=error_frame(
                ProtocolError(
                    "E_INVALID_MESSAGE",
                    "device_id must be a non-empty string",
                    request_id if isinstance(request_id, str) else None,
                )
            ),
        )
    if not isinstance(text, str) or not text.strip():
        return JSONResponse(
            status_code=400,
            content=error_frame(
                ProtocolError(
                    "E_INVALID_MESSAGE",
                    "text must be a non-empty string",
                    request_id if isinstance(request_id, str) else None,
                )
            ),
        )

    device_id = device_id.strip()
    task = create_task_from_transcript(device_id, text.strip(), request_id=request_id if isinstance(request_id, str) else None)
    if task.get("error"):
        _record_device_task_evidence(
            device_id=device_id,
            task=task,
            status="failed",
            request_id=request_id if isinstance(request_id, str) else "",
        )
        return JSONResponse({"status": "failed", "sent": False, "queue_depth": pending_count(device_id), "task": task})
    session = registry.get(device_id)
    sent = False
    if session is not None:
        sent = await dispatch_task_to_session(session, task)
        queue_depth = pending_count(device_id)
    else:
        queue_depth = enqueue_pending_task(device_id, task)
        try:
            await publish_task_available(device_id)
        except Exception as exc:
            _log.warning(
                "publish_task_available failed device=%s task=%s err=%s",
                device_id,
                task.get("task_id", ""),
                type(exc).__name__,
            )
    status = "sent" if sent else "queued"
    _record_device_task_evidence(
        device_id=device_id,
        task=task,
        status=status,
        request_id=request_id if isinstance(request_id, str) else "",
    )
    return JSONResponse({"status": status, "sent": sent, "queue_depth": queue_depth, "task": task})


def _record_device_task_evidence(
    *,
    device_id: str,
    task: dict[str, Any],
    status: str,
    request_id: str = "",
) -> None:
    from observability.capability_evidence import record_evidence_safe

    record_evidence_safe(
        loop="device_gateway",
        request_id=request_id or str(task.get("request_id", "")),
        task_id=str(task.get("task_id", "")),
        device_id=device_id,
        entrypoint="/device/v1/tasks",
        status=status,
        evidence=["device_task_created"],
        rollback="delete pending task queue for test device if smoke-generated",
    )


async def start_device_gateway_runtime() -> None:
    configure_task_store_from_env()
    configure_notifier_from_env()
    await start_task_notifier(notify_local_session_task_available)


async def stop_device_gateway_runtime() -> None:
    await stop_task_notifier()


@router.websocket("/ws")
async def device_ws(websocket: WebSocket) -> None:
    await handle_device_ws(websocket)


def _reset_for_tests() -> None:
    registry.clear()
    reset_tasks_for_tests()
