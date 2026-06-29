"""Device gateway WebSocket uplink loop (CQ-096 facade, CQ-099 handlers).

Supports both text (JSON) frames for device control and binary frames
for audio streaming (PCM 16kHz 16-bit mono).
"""

from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
import logging

from fastapi import WebSocket, WebSocketDisconnect

from device_gateway.protocol import ProtocolError, validate_uplink
from device_gateway.sessions import DeviceSession, registry
from device_gateway.task_events import record_device_disconnected
from routes.device_gateway_dispatch import requeue_session_outstanding, send_ws_error
from routes.device_gateway_ws_handlers import (
    _cleanup_audio_registry,
    _feed_audio_to_pipeline,
    handle_audio_chunk,
    handle_device_info,
    handle_heartbeat,
    handle_hello,
    handle_motion_event,
    handle_self_check,
    handle_transcript,
    handle_voiceprint_sample,
)

try:
    from device_logic.notifications import dispatch_notification
except ImportError as _notifications_import_err:
    logging.warning("device_logic.notifications not available: %s", _notifications_import_err)
    dispatch_notification = None  # type: ignore[misc,assignment]

from device_logic.http import now

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
        await handle_device_info(device_id, message, request_id)
    elif msg_type == "self_check":
        await handle_self_check(device_id, message, request_id)
    elif msg_type == "voiceprint_sample":
        await handle_voiceprint_sample(websocket, device_id, message, request_id)
    elif msg_type == "audio":
        return await handle_audio_chunk(websocket, device_id, message, request_id)
    return True


async def _handle_text_frame(
    websocket: WebSocket,
    raw: dict,
    device_id: str | None,
    session: DeviceSession | None,
    authenticated: bool,
) -> tuple[str | None, DeviceSession | None, bool, bool]:
    """Process a single JSON text frame. Returns (device_id, session, authenticated, keep_open)."""
    try:
        message = validate_uplink(raw)
    except ProtocolError as exc:
        await send_ws_error(websocket, exc)
        return device_id, session, authenticated, True

    msg_type = message["type"]
    request_id = message.get("request_id")

    if msg_type == "hello":
        device_id, session, keep_open = await handle_hello(websocket, message, request_id=request_id)
        if not keep_open:
            return device_id, session, False, False
        authenticated = device_id is not None
        return device_id, session, authenticated, True

    if not authenticated or not device_id:
        await send_ws_error(
            websocket,
            ProtocolError("E_HELLO_REQUIRED", "hello must be sent before other messages", request_id),
        )
        return device_id, session, authenticated, True

    if message["device_id"] != device_id:
        await send_ws_error(
            websocket,
            ProtocolError("E_DEVICE_MISMATCH", "message device_id does not match session", request_id),
        )
        return device_id, session, authenticated, True

    if not await _dispatch_authenticated_message(websocket, device_id, message, request_id):
        return device_id, session, authenticated, False
    return device_id, session, authenticated, True


async def _receive_with_idle_timeout(websocket: WebSocket, authenticated: bool):
    """AUDIT-11-W1：receive 加超时防 Slowloris。返回 (data, timed_out)。"""
    recv_timeout = 600 if authenticated else 60
    try:
        data = await asyncio.wait_for(websocket.receive(), timeout=recv_timeout)
        return data, False
    except asyncio.TimeoutError:
        return None, True


async def handle_device_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    device_id: str | None = None
    session: DeviceSession | None = None
    authenticated = False
    try:
        while True:
            # AUDIT-11-W1：receive 加超时，防 Slowloris 慢速攻击（超时逻辑提取到 helper）
            data, timed_out = await _receive_with_idle_timeout(websocket, authenticated)
            if timed_out:
                await send_ws_error(
                    websocket,
                    ProtocolError("E_IDLE_TIMEOUT", "connection idle too long", None),
                )
                break

            if data is None:
                break

            if data.get("type") == "websocket.disconnect":
                break

            if "bytes" in data:
                # Binary frame → raw PCM audio chunk
                if authenticated and device_id:
                    await _feed_audio_to_pipeline(websocket, device_id, data["bytes"])
            elif "text" in data:
                try:
                    raw = json.loads(data["text"])
                except JSONDecodeError:
                    await send_ws_error(
                        websocket,
                        ProtocolError("E_INVALID_JSON", "text frame must contain a JSON object", None),
                    )
                    continue
                device_id, session, authenticated, keep_open = await _handle_text_frame(
                    websocket, raw, device_id, session, authenticated
                )
                if not keep_open:
                    return
    except WebSocketDisconnect:
        _log.debug("device websocket disconnected device=%s", device_id or "unknown")
    finally:
        if session is not None:
            requeue_session_outstanding(session)
        if device_id:
            _cleanup_audio_registry(device_id)
            registry.unregister(device_id, websocket)
            record_device_disconnected(device_id)
            await _try_dispatch_offline_notification(device_id)


async def _try_dispatch_offline_notification(device_id: str) -> None:
    """Best-effort offline push notification for a disconnected device."""
    if dispatch_notification is None:
        return
    data = {
        "device_name": device_id,
        "device_id": device_id,
        "offline_at": now(),
    }
    try:
        await dispatch_notification(device_id, "device_offline", data)
    except Exception as exc:
        _log.warning(
            "offline notification dispatch failed for device=%s: %s",
            device_id,
            exc,
            exc_info=True,
        )
