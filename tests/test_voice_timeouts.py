"""Voice deadlines stop stalled ASR and idle WebSocket sessions."""

from __future__ import annotations

import asyncio

import pytest
from starlette.websockets import WebSocketState

from config.voice_settings import VOICE
from device_voice import asr
from routes.device_app_voice_ws import _voice_receive_loop


class _NeverProvider:
    async def transcribe(self, _audio_data: bytes) -> str:
        await asyncio.Event().wait()
        return "unreachable"


@pytest.mark.asyncio
async def test_transcribe_audio_times_out_stalled_provider(monkeypatch) -> None:
    monkeypatch.setattr(asr, "get_asr_provider", lambda: _NeverProvider())
    monkeypatch.setattr(VOICE, "asr_timeout_seconds", 0.01)
    with pytest.raises(asyncio.TimeoutError):
        await asr.transcribe_audio(b"audio")


class _IdleWebSocket:
    application_state = WebSocketState.CONNECTED

    def __init__(self) -> None:
        self.closed: tuple[int, str] | None = None

    async def receive(self):
        await asyncio.Event().wait()

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)
        self.application_state = WebSocketState.DISCONNECTED

    async def send_json(self, _payload) -> None:
        return None


@pytest.mark.asyncio
async def test_voice_receive_loop_closes_idle_session(monkeypatch) -> None:
    websocket = _IdleWebSocket()
    monkeypatch.setattr(VOICE, "ws_idle_timeout_seconds", 0.01)
    monkeypatch.setattr(VOICE, "ws_session_timeout_seconds", 1.0)
    await _voice_receive_loop(websocket, object(), {"id": "a-1"})
    assert websocket.closed == (1001, "voice session idle timeout")
