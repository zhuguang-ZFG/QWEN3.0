"""Device gateway WebSocket uplink loop (CQ-096 facade, CQ-099 handlers)."""

from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

from device_gateway.protocol import ProtocolError, validate_uplink
from device_gateway.sessions import DeviceSession, registry
from routes.device_gateway_dispatch import requeue_session_outstanding, send_ws_error
from routes.device_gateway_ws_handlers import (
    handle_device_info,
    handle_heartbeat,
    handle_hello,
    handle_motion_event,
    handle_self_check,
    handle_transcript,
)

_log = logging.getLogger(__name__)


async def _dispatch_authenticated_message(
    websocket: WebSocket,
    device_id: str,
    message: dict,
    request_id: str | None,
) -> bool:
    msg_type = message["type"]
    if msg_type == "heartbeat":
        await handle_heartbeat(websocket, device_id, message, request_id)
    elif msg_type == "transcript":
        return await handle_transcript(websocket, device_id, message, request_id)
    elif msg_type == "motion_event":
        await handle_motion_event(device_id, message, request_id)
    elif msg_type == "device_info":
        await handle_device_info(device_id, request_id)
    elif msg_type == "self_check":
        await handle_self_check(device_id, message, request_id)
    return True


async def handle_device_ws(websocket: WebSocket) -> None:
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
                await send_ws_error(websocket, exc)
                continue

            msg_type = message["type"]
            request_id = message.get("request_id")

            if msg_type == "hello":
                device_id, session, keep_open = await handle_hello(websocket, message, request_id=request_id)
                if not keep_open:
                    return
                authenticated = device_id is not None
                continue

            if not authenticated or not device_id:
                await send_ws_error(
                    websocket,
                    ProtocolError("E_HELLO_REQUIRED", "hello must be sent before other messages", request_id),
                )
                continue

            if message["device_id"] != device_id:
                await send_ws_error(
                    websocket,
                    ProtocolError("E_DEVICE_MISMATCH", "message device_id does not match session", request_id),
                )
                continue

            if not await _dispatch_authenticated_message(websocket, device_id, message, request_id):
                return
    except WebSocketDisconnect:
        _log.debug("device websocket disconnected device=%s", device_id or "unknown")
    finally:
        if session is not None:
            requeue_session_outstanding(session)
        if device_id:
            registry.unregister(device_id, websocket)
