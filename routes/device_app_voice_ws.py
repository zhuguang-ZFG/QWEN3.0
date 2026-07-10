"""Device-app realtime voice WebSocket (M2 streaming ASR)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

import rate_limiter
import voice_app_ws_ticket
import voice_ws_connections
from config.settings import SECURITY
from config.voice_settings import VOICE
from device_logic.auth import load_active_account
from device_voice.asr import AsrNotConfiguredError
from device_voice.streaming_asr import BufferedVoiceStreamSession, DashScopeLiveStreamSession, open_voice_stream_session

router = APIRouter(prefix="/device/v1/app", tags=["device-app-voice-ws"])
legacy_router = APIRouter(tags=["voice-legacy-ws"])

_log = logging.getLogger(__name__)
_WS_RATE_CLOSE = 4429


def _ws_connect_per_min() -> int:
    if VOICE.ws_connect_per_min > 0:
        return VOICE.ws_connect_per_min
    return max(1, VOICE.transcribe_per_min * 3)


def _authorize_voice_ws(websocket: WebSocket) -> dict[str, Any] | None:
    ticket = websocket.query_params.get("ticket", "").strip()
    if not ticket:
        return None
    account_id = voice_app_ws_ticket.peek(ticket)
    if not account_id:
        return None
    account = load_active_account(account_id)
    if not isinstance(account, dict):
        return None
    if voice_app_ws_ticket.consume(ticket) != account_id:
        return None
    return account


def _allow_voice_ws_connect(account_id: str) -> bool:
    if SECURITY.rate_limit_disable:
        return True
    key = f"device_app_voice_ws:{account_id}"
    return rate_limiter.check_keyed_rate_limit(
        key,
        max_per_window=_ws_connect_per_min(),
        window=60.0,
    )


async def _send_transcript(websocket: WebSocket, text: str, *, is_final: bool) -> None:
    await websocket.send_json({"type": "transcript", "text": text, "is_final": is_final})


async def _send_asr_error(websocket: WebSocket, exc: ValueError | RuntimeError) -> None:
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_json({"type": "error", "message": str(exc)})


async def handle_voice_stream_ws(websocket: WebSocket) -> None:
    account = _authorize_voice_ws(websocket)
    if account is None:
        await websocket.close(code=4401)
        return

    account_id = str(account["id"])
    if not _allow_voice_ws_connect(account_id):
        await websocket.close(code=_WS_RATE_CLOSE)
        return
    if not voice_ws_connections.try_acquire(account_id, max_concurrent=VOICE.ws_max_concurrent):
        await websocket.close(code=_WS_RATE_CLOSE)
        return

    try:
        await _run_voice_stream_ws(websocket, account)
    finally:
        voice_ws_connections.release(account_id)


async def _run_voice_stream_ws(websocket: WebSocket, account: dict[str, Any]) -> None:
    try:
        session = await open_voice_stream_session()
    except AsrNotConfiguredError as exc:
        _log.warning("voice ws unavailable: %s", exc)
        await websocket.close(code=1013)
        return

    await websocket.accept()
    live = isinstance(session, DashScopeLiveStreamSession)

    async def on_partial(text: str, is_final: bool) -> None:
        await _send_transcript(websocket, text, is_final=is_final)

    if live:
        await session.start(on_partial)

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                payload = message["bytes"]
                if len(payload) > VOICE.max_audio_bytes:
                    await _send_asr_error(
                        websocket,
                        ValueError(f"audio frame exceeds max size ({VOICE.max_audio_bytes} bytes)"),
                    )
                    break
                try:
                    await session.feed(payload)
                except ValueError as exc:
                    await _send_asr_error(websocket, exc)
                    break
                continue
            text = str(message.get("text") or "").strip().lower()
            if text in {"ping", "heartbeat"}:
                await websocket.send_json({"type": "pong"})
                continue
            if text == "stop":
                try:
                    final_text = await session.finish()
                except (ValueError, RuntimeError) as exc:
                    await _send_asr_error(websocket, exc)
                    break
                if final_text:
                    await _send_transcript(websocket, final_text, is_final=True)
                break
    except WebSocketDisconnect:
        _log.debug("voice ws disconnected account=%s", account.get("id"))
    except Exception as exc:
        _log.warning("voice ws error account=%s: %s", account.get("id"), type(exc).__name__, exc_info=True)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json({"type": "error", "message": "ASR failed"})
    finally:
        if isinstance(session, DashScopeLiveStreamSession):
            await session.close()
        elif isinstance(session, BufferedVoiceStreamSession):
            try:
                final_text = await session.finish()
                if final_text and websocket.client_state == WebSocketState.CONNECTED:
                    await _send_transcript(websocket, final_text, is_final=True)
            except (ValueError, RuntimeError) as exc:
                await _send_asr_error(websocket, exc)
            except Exception as exc:
                _log.warning("voice ws finalize failed: %s", type(exc).__name__)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@router.websocket("/voice/ws")
async def device_app_voice_ws(websocket: WebSocket) -> None:
    await handle_voice_stream_ws(websocket)


@legacy_router.websocket("/v1/voice")
async def legacy_voice_ws(websocket: WebSocket) -> None:
    """Mini-program M2 compatibility alias for realtime voice streaming."""
    await handle_voice_stream_ws(websocket)
