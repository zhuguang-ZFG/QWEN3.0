"""M1 device WebSocket: /device/v1/ws ticket + hello + motion_task push path."""

from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

from device_gateway.auth import validate_device_token
from device_gateway.protocol_min import ProtocolError, ack_frame, hello_ack
from device_gateway.sessions import DeviceSession, registry
from device_gateway.task_events import record_device_connected, record_device_disconnected, record_motion_event
from device_ws_ticket import TTL_SECONDS, issue as issue_device_ws_ticket
from routes.device_gateway_dispatch import (
    drain_pending_tasks,
    extract_ws_token,
    requeue_session_outstanding,
    send_ws_error,
    ticket_device_id,
)
from routes.json_body import read_json_object
from routes.rate_limit_helper import check_key_limit

router = APIRouter(tags=["device-ws"])
_log = logging.getLogger(__name__)


@router.post("/device/v1/ws/ticket")
async def issue_ws_ticket(
    request: Request,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Issue a one-time ticket for device WS (Bearer = device token)."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    device_id = str(body.get("device_id", "")).strip()
    scheme, _, token = authorization.partition(" ")
    token = token.strip() if scheme.lower() == "bearer" else authorization.strip()
    if not device_id or not token:
        return JSONResponse(status_code=400, content={"detail": "device_id and Bearer token required"})
    if not validate_device_token(device_id, token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    limited = check_key_limit(f"device_ws_ticket:{device_id}", 30)
    if limited is not None:
        return limited
    return JSONResponse({"ticket": issue_device_ws_ticket(device_id, token), "expires_in": TTL_SECONDS})


async def _handle_hello(websocket: WebSocket, message: dict[str, Any]) -> tuple[str | None, DeviceSession | None, bool]:
    device_id = str(message.get("device_id", "")).strip()
    request_id = message.get("request_id")
    if not device_id:
        await send_ws_error(websocket, ProtocolError("E_BAD_PARAMS", "hello requires device_id", request_id))
        await websocket.close(code=1008)
        return None, None, False

    bound = ticket_device_id(websocket)
    if bound and bound != device_id:
        await send_ws_error(
            websocket,
            ProtocolError("E_UNAUTHORIZED_DEVICE", "device ticket does not match device_id", request_id),
        )
        await websocket.close(code=1008)
        return None, None, False

    token = extract_ws_token(websocket)
    if not validate_device_token(device_id, token):
        await send_ws_error(
            websocket,
            ProtocolError("E_UNAUTHORIZED_DEVICE", "device token is invalid", request_id),
        )
        await websocket.close(code=1008)
        return None, None, False

    session = DeviceSession(
        device_id=device_id,
        websocket=websocket,
        fw_rev=str(message.get("fw_rev") or message.get("firmwareVersion") or ""),
        capabilities=list(message.get("capabilities") or []),
        protocol_version=str(message.get("protocol") or "lima-device-v1"),
    )
    previous = registry.register(session)
    if previous == "too_many":
        await send_ws_error(websocket, ProtocolError("E_TOO_MANY", "too many device sessions", request_id))
        await websocket.close(code=1008)
        return None, None, False
    if isinstance(previous, DeviceSession) and previous.websocket is not websocket:
        try:
            await previous.websocket.close(code=1012)
        except Exception as exc:
            _log.warning("close superseded websocket device=%s: %s", device_id, exc)

    record_device_connected(device_id)
    await session.send_json(hello_ack(device_id, protocol_version=session.protocol_version))
    if not await drain_pending_tasks(session):
        return device_id, session, False
    return device_id, session, True


async def _handle_message(
    websocket: WebSocket,
    message: dict[str, Any],
    device_id: str | None,
    session: DeviceSession | None,
    authenticated: bool,
) -> tuple[str | None, DeviceSession | None, bool, bool]:
    msg_type = str(message.get("type") or "")
    request_id = message.get("request_id")

    if msg_type == "hello":
        device_id, session, keep = await _handle_hello(websocket, message)
        return device_id, session, device_id is not None, keep

    if not authenticated or not device_id or session is None:
        await send_ws_error(
            websocket,
            ProtocolError("E_HELLO_REQUIRED", "hello must be sent before other messages", request_id),
        )
        return device_id, session, authenticated, True

    if str(message.get("device_id") or device_id) != device_id:
        await send_ws_error(
            websocket,
            ProtocolError("E_DEVICE_MISMATCH", "message device_id does not match session", request_id),
        )
        return device_id, session, authenticated, True

    if msg_type == "heartbeat":
        uptime = int(message.get("uptime_ms") or 0)
        registry.update_heartbeat(device_id, uptime)
        await session.send_json(ack_frame("heartbeat_ack", device_id, uptime_ms=uptime, request_id=request_id))
        return device_id, session, authenticated, True

    if msg_type == "motion_event":
        # Ensure device_id on event for store
        event = dict(message)
        event.setdefault("device_id", device_id)
        if "task_id" in event:
            try:
                record_motion_event(event)
            except Exception as exc:
                _log.warning("motion_event record failed device=%s: %s", device_id, exc, exc_info=True)
        return device_id, session, authenticated, True

    _log.debug("device ws ignore type=%s device=%s", msg_type, device_id)
    return device_id, session, authenticated, True


@router.websocket("/device/v1/ws")
async def device_ws(websocket: WebSocket) -> None:
    """Device uplink: hello → register → drain pending; downlink motion_task push."""
    await websocket.accept()
    device_id: str | None = None
    session: DeviceSession | None = None
    authenticated = False
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            data = await websocket.receive()
            if data.get("type") == "websocket.disconnect":
                break
            if "text" not in data:
                continue
            try:
                raw = json.loads(data["text"])
            except JSONDecodeError:
                await send_ws_error(
                    websocket,
                    ProtocolError("E_INVALID_JSON", "text frame must contain a JSON object", None),
                )
                continue
            if not isinstance(raw, dict):
                await send_ws_error(
                    websocket,
                    ProtocolError("E_INVALID_JSON", "text frame must be a JSON object", None),
                )
                continue
            device_id, session, authenticated, keep = await _handle_message(
                websocket, raw, device_id, session, authenticated
            )
            if not keep:
                break
    except WebSocketDisconnect:
        _log.debug("device websocket disconnected device=%s", device_id or "unknown")
    finally:
        if session is not None:
            requeue_session_outstanding(session)
        if device_id:
            registry.unregister(device_id, websocket)
            record_device_disconnected(device_id)
