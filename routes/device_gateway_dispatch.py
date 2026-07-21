"""Device session dispatch: push motion_task to online WebSocket sessions (M1)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    mark_task_dispatched,
    pending_count,
    pop_pending_tasks,
    requeue_pending_tasks,
)
from device_ws_ticket import consume as consume_device_ws_ticket
from observability import prometheus_metrics

_log = logging.getLogger(__name__)

MAX_TASK_RETRIES = 3


def _ws_state(websocket: WebSocket) -> dict:
    return websocket.scope.setdefault("state", {})


def ticket_device_id(websocket: WebSocket) -> str | None:
    value = _ws_state(websocket).get("ticket_device_id")
    return str(value) if value else None


def extract_ws_token(websocket: WebSocket) -> str:
    """Prefer one-time ticket; else Authorization Bearer. No query tokens."""
    ticket = websocket.query_params.get("ticket", "").strip()
    if ticket:
        redeemed = consume_device_ws_ticket(ticket)
        if redeemed:
            device_id, token = redeemed
            _ws_state(websocket)["ticket_device_id"] = device_id
            return token

    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if authorization.strip():
        _log.warning("device WS authorization missing Bearer prefix")
        return authorization.strip()
    return ""


async def send_ws_error(websocket: WebSocket, error: Exception, request_id: str | None = None) -> None:
    from device_gateway.protocol_min import ProtocolError, error_frame

    await websocket.send_json(error_frame(error if isinstance(error, ProtocolError) else error, request_id))


def requeue_session_outstanding(
    session: DeviceSession,
    extra_tasks: list[dict[str, Any]] | None = None,
) -> int:
    outstanding = session.take_outstanding_tasks()
    tasks = [*outstanding, *(extra_tasks or [])]
    if not tasks:
        return pending_count(session.device_id)

    from device_gateway.store import task_store

    to_requeue: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        capability = str(task.get("capability", "unknown"))
        retry_count = task_store.increment_retry_count(task_id)
        prometheus_metrics.record_device_task_retry(capability)
        if retry_count > MAX_TASK_RETRIES:
            _log.warning("task %s exceeded max retries", task_id)
            prometheus_metrics.record_device_task_dead_letter(capability)
            task_store.abandon_processing_task(session.device_id, task_id)
            continue
        to_requeue.append(task)

    if not to_requeue:
        return pending_count(session.device_id)
    return requeue_pending_tasks(session.device_id, to_requeue)


async def dispatch_task_to_session(session: DeviceSession, task: dict[str, Any]) -> bool:
    """Send one motion_task JSON frame to an online session."""
    capability = str(task.get("capability", "unknown"))
    payload = dict(task)
    payload.setdefault("type", "motion_task")
    try:
        await session.send_json(payload)
    except Exception as exc:
        _log.warning(
            "dispatch task failed device=%s task=%s: %s",
            session.device_id,
            task.get("task_id", ""),
            exc,
            exc_info=True,
        )
        prometheus_metrics.record_device_task_dispatch_failure("websocket_error")
        registry.unregister(session.device_id, session.websocket)
        requeue_session_outstanding(session, [task])
        return False
    session.mark_task_dispatched(task)
    mark_task_dispatched(task["task_id"])
    prometheus_metrics.record_device_task_dispatched(capability, "sent")
    return True


async def drain_pending_tasks(session: DeviceSession) -> bool:
    """Pop pending queue and push each task to the device. True if all sent."""
    while True:
        pending_tasks = pop_pending_tasks(session.device_id)
        if not pending_tasks:
            return True
        for index, pending_task in enumerate(pending_tasks):
            ok = await dispatch_task_to_session(session, pending_task)
            if not ok:
                # Remaining already requeued by dispatch failure for current;
                # requeue unsent tail if any still in this batch.
                rest = pending_tasks[index + 1 :]
                if rest:
                    requeue_session_outstanding(session, rest)
                return False
    return True


async def try_deliver_pending(device_id: str) -> bool:
    """If device has an online session, drain its pending queue. Else False."""
    session = registry.get(device_id)
    if session is None:
        return False
    try:
        return await drain_pending_tasks(session)
    except Exception as exc:
        _log.exception("try_deliver_pending failed device=%s: %s", device_id, type(exc).__name__)
        return False
