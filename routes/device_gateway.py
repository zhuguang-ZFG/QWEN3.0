"""LiMa direct device gateway HTTP routes."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Query, Request, WebSocket
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_intelligence.shadow import shadow_store
from device_gateway.auth import token_configured
from device_gateway.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    ack_frame,
    error_frame,
    validate_uplink,
)
from device_gateway.sessions import registry
from device_gateway.store import configure_task_store_from_env, task_store_health
from device_ledger.store import configure_ledger_store_from_env, ledger_store_health
from device_memory.store import configure_memory_store_from_env, memory_store_health
from device_gateway.notifier import (
    configure_notifier_from_env,
    notifier_health,
    start_task_notifier,
    stop_task_notifier,
)
from device_gateway.task_service import DeviceTaskRequest, create_and_route_task
from device_gateway.health import build_device_gateway_health
from device_gateway.tasks import (
    ack_processing_task,
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
from routes.json_body import read_json_object

router = APIRouter(prefix="/device/v1")

# Back-compat for tests
_dispatch_task_to_session = dispatch_task_to_session
_drain_pending_tasks = drain_pending_tasks
_notify_local_session_task_available = notify_local_session_task_available


@router.get("/health", response_model=None)
async def device_gateway_health() -> dict[str, Any] | JSONResponse:
    payload, production_ready = build_device_gateway_health()
    if not production_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.post("/events", dependencies=[Depends(require_private_api_key)])
async def device_gateway_events(request: Request) -> JSONResponse:
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        message = validate_uplink(body)
    except ProtocolError as exc:
        return JSONResponse(status_code=400, content=error_frame(exc))

    msg_type = message["type"]
    device_id = message.get("device_id", "")
    if msg_type == "motion_event":
        summary = record_motion_event(message)
        shadow_store.update_motion_event(message)
        ack_processing_task(device_id, message["task_id"])
        record_motion_event_observability(message, device_id)
        return JSONResponse(ack_frame("motion_event_ack", device_id, **summary, request_id=message.get("request_id")))
    if msg_type == "device_info":
        shadow_store.update_device_info(message)
        return JSONResponse(ack_frame("device_info_ack", device_id, request_id=message.get("request_id")))
    if msg_type == "self_check":
        shadow_store.update_self_check(message)
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
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
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
    result = await create_and_route_task(
        DeviceTaskRequest(
            device_id=device_id,
            text=text.strip(),
            request_id=request_id if isinstance(request_id, str) else "",
        )
    )
    _record_device_task_evidence(
        device_id=device_id,
        task=result.task,
        status=result.status,
        request_id=request_id if isinstance(request_id, str) else "",
    )
    return JSONResponse(
        {
            "status": result.status,
            "sent": result.sent,
            "queue_depth": result.queue_depth,
            "task": result.task,
        }
    )


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
    configure_memory_store_from_env()
    configure_ledger_store_from_env()
    configure_notifier_from_env()
    await start_task_notifier(notify_local_session_task_available)


async def stop_device_gateway_runtime() -> None:
    await stop_task_notifier()


@router.websocket("/ws")
async def device_ws(websocket: WebSocket) -> None:
    await handle_device_ws(websocket)


@router.get("/tasks/{task_id}", dependencies=[Depends(require_private_api_key)])
async def device_task_status(task_id: str) -> JSONResponse:
    """查询任务状态"""
    from device_gateway.tasks import task_snapshot

    snapshot = task_snapshot(task_id)
    if not snapshot:
        return JSONResponse(
            status_code=404,
            content=error_frame(ProtocolError("E_TASK_NOT_FOUND", f"Task {task_id} not found")),
        )

    return JSONResponse(
        {
            "task_id": task_id,
            "status": snapshot.get("status", "unknown"),
            "task": snapshot.get("task", {}),
            "events": snapshot.get("events", []),
        }
    )


@router.get("/tasks", dependencies=[Depends(require_private_api_key)])
async def device_task_list(
    device_id: str = "",
    status: str = "",
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """查询任务列表"""
    from device_gateway.store import task_store

    if not device_id:
        return JSONResponse({"tasks": [], "count": 0})

    tasks = task_store.list_tasks_for_device(device_id, status=status, limit=limit)

    return JSONResponse(
        {
            "tasks": tasks,
            "count": len(tasks),
        }
    )


@router.get("/devices/{device_id}/history", dependencies=[Depends(require_private_api_key)])
async def device_drawing_history(
    device_id: str,
    artifact_type: str = "",
    limit: int = 20,
    offset: int = 0,
) -> JSONResponse:
    """查询设备绘图历史"""
    from device_artifacts.store import artifacts_for_device

    artifacts = artifacts_for_device(
        device_id=device_id,
        artifact_type=artifact_type if artifact_type else None,
        limit=limit,
        offset=offset,
    )

    # 转换为可序列化的格式
    history = []
    for artifact in artifacts:
        history.append(
            {
                "task_id": artifact.task_id,
                "artifact_type": artifact.artifact_type,
                "content": artifact.content,
                "content_hash": artifact.content_hash,
                "created_at": artifact.created_at,
            }
        )

    return JSONResponse(
        {
            "device_id": device_id,
            "history": history,
            "count": len(history),
            "offset": offset,
            "limit": limit,
        }
    )


def _reset_for_tests() -> None:
    registry.clear()
    reset_tasks_for_tests()
    shadow_store.reset()
