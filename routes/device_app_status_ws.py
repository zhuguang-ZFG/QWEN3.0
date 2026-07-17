"""LiMa native device app real-time status WebSocket (M2)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from access_guard import extract_bearer_token
from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

import app_status_ws_ticket
import app_status_ws_connections
from config.settings import DEVICE
from device_logic.access import require_device_access
from device_logic.auth import authorize, load_active_account
from device_logic.db import connect
from routes.rate_limit_helper import check_key_limit
from device_logic.http import now
from routes.device_app_api import _build_device_status

router = APIRouter(prefix="/device/v1/app", tags=["device-app-status"])

_log = logging.getLogger(__name__)

# Polling interval for status snapshots. Tests may monkeypatch this to speed up transitions.
_POLL_INTERVAL = 5.0


def _query_token_auth_enabled() -> bool:
    return os.environ.get("LIMA_DEVICE_APP_WS_QUERY_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}


async def _authorize_ws(websocket: WebSocket, device_id: str) -> dict[str, Any] | None:
    """Validate ticket/query-token without consuming; return active account."""
    ticket = websocket.query_params.get("ticket", "").strip()
    if ticket:
        peeked = app_status_ws_ticket.peek(ticket)
        if peeked:
            redeemed_device_id, account_id = peeked
            if redeemed_device_id == device_id:
                account = load_active_account(account_id)
                if isinstance(account, dict):
                    with connect() as conn:
                        denied = require_device_access(conn, account, device_id)
                    if denied is None:
                        return account
        return None

    if not _query_token_auth_enabled():
        return None

    auth_query = websocket.query_params.get("authorization", "").strip()
    if auth_query:
        _log.warning(
            "device app status WS token exposed in query string for device=%s; prefer /ws/ticket",
            device_id,
        )
    token = extract_bearer_token(auth_query)
    if not token:
        return None
    account = authorize(f"Bearer {token}")
    if isinstance(account, dict):
        with connect() as conn:
            denied = require_device_access(conn, account, device_id)
        if denied is None:
            return account
    return None


def _consume_status_ticket_if_present(
    websocket: WebSocket,
    device_id: str,
    account_id: str,
) -> bool:
    """Consume one-time ticket after slot acquire; query-token path is a no-op."""
    ticket = websocket.query_params.get("ticket", "").strip()
    if not ticket:
        return True
    redeemed = app_status_ws_ticket.consume(ticket)
    if not redeemed:
        return False
    redeemed_device_id, redeemed_account_id = redeemed
    return redeemed_device_id == device_id and redeemed_account_id == account_id


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


@router.post("/devices/{device_id}/ws/ticket")
async def issue_device_status_ws_ticket(
    request: Request,
    device_id: str,
) -> JSONResponse:
    """Exchange a user token for a one-time device status WebSocket ticket."""
    from routes.json_body import read_json_object

    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    header_token = request.headers.get("authorization", "")
    token = extract_bearer_token(header_token) or str(body.get("token", "")).strip()
    account = authorize(f"Bearer {token}") if token else None
    if not isinstance(account, dict):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    limited = check_key_limit(f"device_app_status_ticket:{account['id']}:{device_id}", DEVICE.status_ws_ticket_per_min)
    if limited is not None:
        return limited
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
    if denied is not None:
        return JSONResponse(status_code=403, content={"detail": "Access denied"})
    return JSONResponse(
        {
            "ticket": app_status_ws_ticket.issue(device_id, account["id"]),
            "expires_in": app_status_ws_ticket.TTL_SECONDS,
        }
    )


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

    account = await _authorize_ws(websocket, device_id)
    if not account:
        await websocket.close(code=1008)
        return

    account_id = str(account["id"])
    if not app_status_ws_connections.try_acquire(account_id, device_id, max_concurrent=DEVICE.status_ws_max_concurrent):
        await websocket.close(code=4429)
        return

    try:
        if not _consume_status_ticket_if_present(websocket, device_id, account_id):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        deadline = asyncio.get_running_loop().time() + DEVICE.status_ws_session_seconds
        previous = await asyncio.to_thread(_build_device_status, device_id)
        await _send_status_snapshot(websocket, device_id, previous)
        while websocket.client_state == WebSocketState.CONNECTED:
            if asyncio.get_running_loop().time() >= deadline:
                await websocket.close(code=1001, reason="status session expired")
                break
            await asyncio.sleep(_POLL_INTERVAL)
            current = await asyncio.to_thread(_build_device_status, device_id)
            await _push_transition_events(websocket, device_id, previous, current)
            previous = current
            await _send_status_snapshot(websocket, device_id, current)
    except WebSocketDisconnect:
        _log.debug("device status ws disconnected device=%s", device_id)
    except Exception as exc:
        _log.warning("device status ws error device=%s: %s", device_id, exc)
    finally:
        app_status_ws_connections.release(account_id, device_id)
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except Exception as close_exc:
            _log.warning("device status ws close failed device=%s: %s", device_id, close_exc)
