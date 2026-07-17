"""Device-app realtime voice WebSocket (M2 streaming ASR)."""

from __future__ import annotations

import asyncio
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
    """Peek-only ticket auth; consume happens after slot + ASR succeed."""
    ticket = websocket.query_params.get("ticket", "").strip()
    if not ticket:
        return None
    account_id = voice_app_ws_ticket.peek(ticket)
    if not account_id:
        return None
    account = load_active_account(account_id)
    if not isinstance(account, dict):
        return None
    return account


def _consume_voice_ticket(websocket: WebSocket, account_id: str) -> bool:
    ticket = websocket.query_params.get("ticket", "").strip()
    return voice_app_ws_ticket.consume_if(ticket, lambda aid: aid == account_id) == account_id


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


async def _send_asr_error(websocket: WebSocket, exc: ValueError | RuntimeError | asyncio.TimeoutError) -> None:
    if websocket.application_state == WebSocketState.CONNECTED:
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


async def _create_asr_session(websocket: WebSocket) -> Any | None:
    try:
        return await open_voice_stream_session()
    except AsrNotConfiguredError as exc:
        _log.warning("voice ws unavailable: %s", exc)
        await websocket.close(code=1013)
        return None


async def _start_dashscope_if_needed(websocket: WebSocket, session: Any) -> bool:
    if not isinstance(session, DashScopeLiveStreamSession):
        return True

    async def on_partial(text: str, is_final: bool) -> None:
        await _send_transcript(websocket, text, is_final=is_final)

    try:
        await asyncio.wait_for(session.start(on_partial), timeout=VOICE.asr_timeout_seconds)
    except (asyncio.TimeoutError, ValueError, RuntimeError) as exc:
        _log.warning("voice ws session.start failed: %s", exc)
        await websocket.close(code=1011, reason="ASR start timeout")
        return False
    return True


async def _handle_audio_frame(websocket: WebSocket, session: Any, payload: bytes) -> bool:
    """Feed one audio frame. Returns False when the stream should stop."""
    if len(payload) > VOICE.max_audio_bytes:
        await _send_asr_error(
            websocket,
            ValueError(f"audio frame exceeds max size ({VOICE.max_audio_bytes} bytes)"),
        )
        return False
    try:
        await asyncio.wait_for(session.feed(payload), timeout=VOICE.asr_timeout_seconds)
    except (ValueError, asyncio.TimeoutError) as exc:
        await _send_asr_error(websocket, exc)
        return False
    return True


async def _handle_control_text(websocket: WebSocket, session: Any, text: str) -> bool:
    """Handle text control frames. Returns False when the stream should stop."""
    if text in {"ping", "heartbeat"}:
        await websocket.send_json({"type": "pong"})
        return True
    if text != "stop":
        return True
    try:
        final_text = await asyncio.wait_for(session.finish(), timeout=VOICE.asr_timeout_seconds)
    except (ValueError, RuntimeError, asyncio.TimeoutError) as exc:
        await _send_asr_error(websocket, exc)
        return False
    if final_text:
        await _send_transcript(websocket, final_text, is_final=True)
    return False


async def _voice_receive_loop(websocket: WebSocket, session: Any, account: dict[str, Any]) -> None:
    total_bytes = 0
    session_limit = VOICE.max_audio_bytes * 10
    loop = asyncio.get_running_loop()
    session_deadline = loop.time() + VOICE.ws_session_timeout_seconds
    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            remaining = session_deadline - loop.time()
            if remaining <= 0:
                await websocket.close(code=1001, reason="voice session expired")
                break
            try:
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=min(VOICE.ws_idle_timeout_seconds, remaining)
                )
            except asyncio.TimeoutError:
                await websocket.close(code=1001, reason="voice session idle timeout")
                break
            if message["type"] == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                total_bytes += len(message["bytes"])
                if total_bytes > session_limit:
                    await _send_asr_error(
                        websocket,
                        ValueError("session audio data limit exceeded"),
                    )
                    await websocket.close(code=1009)
                    break
                if not await _handle_audio_frame(websocket, session, message["bytes"]):
                    break
                continue
            text = str(message.get("text") or "").strip().lower()
            if not await _handle_control_text(websocket, session, text):
                break
    except WebSocketDisconnect:
        _log.debug("voice ws disconnected account=%s", account.get("id"))
    except Exception as exc:
        _log.warning("voice ws error account=%s: %s", account.get("id"), type(exc).__name__, exc_info=True)
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_json({"type": "error", "message": "ASR failed"})


async def _finalize_voice_session(websocket: WebSocket, session: Any) -> None:
    if isinstance(session, DashScopeLiveStreamSession):
        try:
            await asyncio.wait_for(session.close(), timeout=VOICE.asr_timeout_seconds)
        except Exception as exc:
            _log.warning("voice ws dashscope session close failed: %s", type(exc).__name__)
    elif isinstance(session, BufferedVoiceStreamSession):
        try:
            final_text = await asyncio.wait_for(session.finish(), timeout=VOICE.asr_timeout_seconds)
            if final_text and websocket.application_state == WebSocketState.CONNECTED:
                await _send_transcript(websocket, final_text, is_final=True)
        except (ValueError, RuntimeError) as exc:
            await _send_asr_error(websocket, exc)
        except Exception as exc:
            _log.warning("voice ws finalize failed: %s", type(exc).__name__)
    # Only close if still CONNECTED (post-accept). Pre-accept failures already
    # called close(4401/1013); DashScope start failure already close(1011).
    # A blank close() here would overwrite those intentional codes.
    if websocket.application_state == WebSocketState.CONNECTED:
        await websocket.close()


async def _run_voice_stream_ws(websocket: WebSocket, account: dict[str, Any]) -> None:
    """Open ASR, then consume ticket / accept; always abandon session on exit."""
    session = await _create_asr_session(websocket)
    if session is None:
        return
    try:
        account_id = str(account["id"])
        if not _consume_voice_ticket(websocket, account_id):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        if not await _start_dashscope_if_needed(websocket, session):
            return
        await _voice_receive_loop(websocket, session, account)
    finally:
        # Covers consume race, DashScope start failure (1011), and normal exit.
        await _finalize_voice_session(websocket, session)


@router.websocket("/voice/ws")
async def device_app_voice_ws(websocket: WebSocket) -> None:
    await handle_voice_stream_ws(websocket)


@legacy_router.websocket("/v1/voice")
async def legacy_voice_ws(websocket: WebSocket) -> None:
    """Mini-program M2 compatibility alias for realtime voice streaming."""
    await handle_voice_stream_ws(websocket)
