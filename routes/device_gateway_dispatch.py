"""Device gateway session dispatch helpers (CQ-096)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.notifier import publish_task_available
from device_gateway.protocol import ProtocolError, error_frame
from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    mark_task_dispatched,
    pending_count,
    pop_pending_tasks,
    requeue_pending_tasks,
)

_log = logging.getLogger(__name__)


def extract_ws_token(websocket: WebSocket) -> str:
    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if authorization.strip():
        return authorization.strip()
    return websocket.query_params.get("token", "").strip()


async def send_ws_error(
    websocket: WebSocket,
    error: ProtocolError | Exception,
    request_id: str | None = None,
) -> None:
    await websocket.send_json(error_frame(error, request_id=request_id))


def requeue_session_outstanding(
    session: DeviceSession,
    extra_tasks: list[dict[str, Any]] | None = None,
) -> int:
    outstanding = session.take_outstanding_tasks()
    tasks = [*outstanding, *(extra_tasks or [])]
    if not tasks:
        return pending_count(session.device_id)
    return requeue_pending_tasks(session.device_id, tasks)


async def dispatch_task_to_session(session: DeviceSession, task: dict[str, Any]) -> bool:
    try:
        await session.send_json(task)
    except Exception as exc:
        _log.debug(
            "dispatch task failed device=%s task=%s: %s",
            session.device_id,
            task.get("task_id", ""),
            type(exc).__name__,
        )
        registry.unregister(session.device_id, session.websocket)
        requeue_session_outstanding(session, [task])
        return False
    session.mark_task_dispatched(task)
    mark_task_dispatched(task["task_id"])
    return True


async def drain_pending_tasks(session: DeviceSession) -> bool:
    while True:
        pending_tasks = pop_pending_tasks(session.device_id)
        if not pending_tasks:
            return True
        for index, pending_task in enumerate(pending_tasks):
            try:
                await session.send_json(pending_task)
            except Exception as exc:
                _log.debug(
                    "drain pending failed device=%s task=%s: %s",
                    session.device_id,
                    pending_task.get("task_id", ""),
                    type(exc).__name__,
                )
                registry.unregister(session.device_id, session.websocket)
                requeue_session_outstanding(session, pending_tasks[index:])
                return False
            session.mark_task_dispatched(pending_task)
            mark_task_dispatched(pending_task["task_id"])


async def notify_local_session_task_available(device_id: str) -> None:
    try:
        session = registry.get(device_id)
        if session is not None:
            await drain_pending_tasks(session)
    except Exception as exc:
        _log.exception(
            "notify_local_session_task_available failed device=%s: %s",
            device_id,
            type(exc).__name__,
        )


async def publish_task_available_safe(device_id: str, task_id: str = "") -> None:
    try:
        await publish_task_available(device_id)
    except Exception as exc:
        _log.warning(
            "publish_task_available failed device=%s task=%s err=%s",
            device_id,
            task_id,
            type(exc).__name__,
        )


def record_motion_event_observability(message: dict[str, Any], device_id: str) -> None:
    try:
        from observability.correlation import record_motion_event_correlation

        error_code = ""
        error_reason = ""
        err = message.get("error", {}) if isinstance(message.get("error"), dict) else {}
        if not err:
            error_code = message.get("error_code", "")
            error_reason = message.get("error_message", "")
        else:
            error_code = err.get("code", "")
            error_reason = err.get("reason", "")
        record_motion_event_correlation(
            task_id=message["task_id"],
            device_id=device_id,
            phase=message.get("phase", "unknown"),
            error_code=error_code,
            error_reason=error_reason,
        )
    except ImportError:
        _log.debug("observability.correlation not installed")
