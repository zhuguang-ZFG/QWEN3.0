"""LiMa native device app real-time status WebSocket (M2)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from access_guard import extract_bearer_token
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from device_gateway.sessions import registry
from device_gateway.tasks import active_tasks_for_device
from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import now
from routes.device_app_api import _build_device_status

router = APIRouter(prefix="/device/v1/app", tags=["device-app-status"])

_log = logging.getLogger(__name__)

# Polling interval for status snapshots. Tests may monkeypatch this to speed up transitions.
_POLL_INTERVAL = 5.0


async def _authorize_ws(websocket: WebSocket, device_id: str) -> bool:
    """Validate the query-token and device access. Returns True on success."""
    token = extract_bearer_token(websocket.query_params.get("authorization", ""))
    if not token:
        return False
    account = authorize(f"Bearer {token}")
    if isinstance(account, dict):
        with connect() as conn:
            denied = require_device_access(conn, account, device_id)
        if denied is None:
            return True
    return False


async def _send_status_snapshot(
    websocket: WebSocket,
    device_id: str,
    status: dict[str, Any],
) -> None:
    await websocket.send_json({"event": "status_snapshot", "payload": status})


async def _send_online_transition(
    websocket: WebSocket,
    device_id: str,
    online: bool,
) -> None:
    event = "device_online" if online else "device_offline"
    await websocket.send_json({"event": event, "payload": {"deviceId": device_id, "timestamp": now()}})


async def _send_task_transition(
    websocket: WebSocket,
    device_id: str,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> None:
    current_task = current.get("activeTaskId")
    previous_task = previous.get("activeTaskId")
    if current_task == previous_task:
        return
    if current_task:
        payload = {"deviceId": device_id, "taskId": current_task, "timestamp": now()}
        await websocket.send_json({"event": "task_started", "payload": payload})
    else:
        # TODO(M2): distinguish completed vs failed via task terminal events.
        payload = {"deviceId": device_id, "taskId": previous_task, "timestamp": now()}
        await websocket.send_json({"event": "task_completed", "payload": payload})


async def _push_transition_events(
    websocket: WebSocket,
    device_id: str,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> None:
    if current["online"] != previous["online"]:
        await _send_online_transition(websocket, device_id, current["online"])
    await _send_task_transition(websocket, device_id, previous, current)
    # TODO(M2): push task_progress events from task store / session.
    # TODO(M2): push firmware_update events when device reports new fw_rev.


@router.websocket("/devices/{device_id}/ws")
async def device_status_ws(
    websocket: WebSocket,
    device_id: str,
    authorization: str = Query(default=""),
) -> None:
    # `authorization` is declared so FastAPI documents the query parameter;
    # the actual value is read from websocket.query_params to support both
    # header and query-token auth in tests.
    _ = authorization

    if not await _authorize_ws(websocket, device_id):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        previous = _build_device_status(device_id)
        await _send_status_snapshot(websocket, device_id, previous)
        while websocket.client_state == WebSocketState.CONNECTED:
            await asyncio.sleep(_POLL_INTERVAL)
            current = _build_device_status(device_id)
            await _push_transition_events(websocket, device_id, previous, current)
            previous = current
            await _send_status_snapshot(websocket, device_id, current)
    except WebSocketDisconnect:
        _log.debug("device status ws disconnected device=%s", device_id)
    except Exception as exc:
        _log.warning("device status ws error device=%s: %s", device_id, exc)
    finally:
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except Exception as close_exc:
            _log.warning("device status ws close failed device=%s: %s", device_id, close_exc)
