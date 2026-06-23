"""LiMa direct device gateway HTTP routes."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Query, Request, WebSocket
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_intelligence.shadow import shadow_store
from device_gateway.auth import token_configured, validate_device_token
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
from device_gateway.tasks import DeviceTaskRequest, create_and_route_task
from device_gateway.health import build_device_gateway_health
from device_gateway.task_events import process_motion_event_core
from routes.device_gateway_dispatch import (
    dispatch_task_to_session,
    drain_pending_tasks,
    notify_local_session_task_available,
)
from routes.device_gateway_helpers import (
    _record_device_task_evidence,
    _reset_for_tests,
    start_device_gateway_runtime,
    stop_device_gateway_runtime,
)
from routes.device_gateway_ws import handle_device_ws
from routes.json_body import read_json_object

import device_ws_ticket

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
        summary = process_motion_event_core(device_id, message)
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


def _validate_task_body(body: dict[str, Any]) -> tuple[str, str, str] | JSONResponse:
    """Validate device task body and return (device_id, text, request_id) or error."""
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
    return device_id.strip(), text.strip(), request_id if isinstance(request_id, str) else ""


async def _create_and_record_task(device_id: str, text: str, request_id: str) -> JSONResponse:
    """Create and route a device task, recording evidence."""
    result = await create_and_route_task(DeviceTaskRequest(device_id=device_id, text=text, request_id=request_id))
    _record_device_task_evidence(
        device_id=device_id,
        task=result.task,
        status=result.status,
        request_id=request_id,
    )
    return JSONResponse(
        {
            "status": result.status,
            "sent": result.sent,
            "queue_depth": result.queue_depth,
            "task": result.task,
        }
    )


@router.post("/tasks", dependencies=[Depends(require_private_api_key)])
async def device_gateway_tasks(request: Request) -> JSONResponse:
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    validated = _validate_task_body(body)
    if isinstance(validated, JSONResponse):
        return validated
    device_id, text, request_id = validated
    return await _create_and_record_task(device_id, text, request_id)


@router.post("/ws/ticket")
async def create_device_ws_ticket(request: Request) -> JSONResponse:
    """Exchange a device token for a short-lived WebSocket ticket."""
    body = await read_json_object(request)
    device_id = str(body.get("device_id", "")).strip()
    header_token = request.headers.get("authorization", "")
    from access_guard import extract_bearer_token

    token = extract_bearer_token(header_token) or str(body.get("token", "")).strip()
    if not device_id or not validate_device_token(device_id, token):
        return JSONResponse(
            status_code=401,
            content=error_frame(ProtocolError("E_UNAUTHORIZED_DEVICE", "device token is invalid")),
        )
    return JSONResponse(
        {
            "ticket": device_ws_ticket.issue(device_id, token),
            "expires_in": device_ws_ticket.TTL_SECONDS,
        }
    )


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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
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
