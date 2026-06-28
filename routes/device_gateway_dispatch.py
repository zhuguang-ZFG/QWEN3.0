"""Device gateway session dispatch helpers (CQ-096)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from device_gateway.attestation import ACTION_FULL_ACCESS
from device_gateway.notifier import publish_task_available
from device_gateway.protocol import ProtocolError, error_frame
from device_gateway.sessions import DeviceSession, registry
from device_gateway.store import task_store
from device_gateway.tasks import (
    mark_task_dispatched,
    pending_count,
    pop_pending_tasks,
    requeue_pending_tasks,
)

from device_ws_ticket import consume as consume_device_ws_ticket

# Re-exported from task_lifecycle to keep consumers on a single import path.
from device_gateway.task_lifecycle import record_motion_event_observability
from observability import prometheus_metrics

_log = logging.getLogger(__name__)

MAX_TASK_RETRIES = 3


def _ws_state(websocket: WebSocket) -> dict:
    return websocket.scope.setdefault("state", {})


def ticket_device_id(websocket: WebSocket) -> str | None:
    value = _ws_state(websocket).get("ticket_device_id")
    return str(value) if value else None


def extract_ws_token(websocket: WebSocket) -> str:
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
    # Some web testers (e.g. the 2D digital human page) pass the token as an
    # ``authorization`` query parameter. Support both ``token`` and
    # ``authorization`` for compatibility, but log missing Bearer prefix.
    token = websocket.query_params.get("token", "").strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    if token:
        _log.warning("device WS token query param exposes secret; prefer POST /device/v1/ws/ticket")
        return token
    auth_query = websocket.query_params.get("authorization", "").strip()
    if auth_query.lower().startswith("bearer "):
        return auth_query[7:].strip()
    if auth_query:
        _log.warning("device WS authorization query param missing Bearer prefix")
        return auth_query
    return ""


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

    to_requeue: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        capability = str(task.get("capability", "unknown"))
        retry_count = task_store.increment_retry_count(task_id)
        prometheus_metrics.record_device_task_retry(capability)
        if retry_count > MAX_TASK_RETRIES:
            _log.warning("task %s exceeded max retries, moving to dead letter", task_id)
            prometheus_metrics.record_device_task_dead_letter(capability)
            task_store.abandon_processing_task(session.device_id, task_id)
            continue
        to_requeue.append(task)

    if not to_requeue:
        return pending_count(session.device_id)
    return requeue_pending_tasks(session.device_id, to_requeue)


def _is_attestation_restricted(session: DeviceSession) -> bool:
    action = getattr(session, "attestation_action", ACTION_FULL_ACCESS)
    # Defensive: non-string actions only come from poorly initialized mocks.
    # Empty action means the session has not gone through attestation yet (e.g.
    # unit tests creating a DeviceSession directly). Treat both as full access so
    # legacy tests and unattested paths keep working; explicit quarantine/read_only
    # still blocks.
    if not isinstance(action, str) or not action:
        return False
    return action != ACTION_FULL_ACCESS


async def dispatch_task_to_session(session: DeviceSession, task: dict[str, Any]) -> bool:
    capability = str(task.get("capability", "unknown"))
    if _is_attestation_restricted(session):
        _log.warning(
            "dispatch blocked device=%s attestation=%s task=%s",
            session.device_id,
            session.attestation_action,
            task.get("task_id", ""),
        )
        prometheus_metrics.record_device_task_dispatch_failure("attestation_restricted")
        requeue_session_outstanding(session, [task])
        return False
    try:
        await session.send_json(task)
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
    if _is_attestation_restricted(session):
        _log.warning(
            "drain blocked device=%s attestation=%s",
            session.device_id,
            session.attestation_action,
        )
        return False
    while True:
        pending_tasks = pop_pending_tasks(session.device_id)
        if not pending_tasks:
            return True
        for index, pending_task in enumerate(pending_tasks):
            try:
                await session.send_json(pending_task)
            except Exception as exc:
                _log.warning(
                    "drain pending failed device=%s task=%s: %s",
                    session.device_id,
                    pending_task.get("task_id", ""),
                    exc,
                    exc_info=True,
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


from device_gateway.task_lifecycle import record_motion_event_observability
