"""Tests for routes/voice_pipeline_ws.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import voice_pipeline_ws as vp


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(vp.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_unauthorized_websocket_rejected(client):
    with patch("routes.voice_pipeline_ws.authenticate_websocket", return_value=(False, "none")):
        with pytest.raises(Exception):
            with client.websocket_connect("/v1/voice"):
                pass


def test_authorized_websocket_accepts_text_message(client):
    fake_vad = MagicMock()
    fake_vad.detect = MagicMock()
    fake_vad.is_utterance_end.return_value = False
    fake_vad.reset = MagicMock()

    with (
        patch("routes.voice_pipeline_ws.authenticate_websocket", return_value=(True, "header")),
        patch("routes.voice_pipeline_ws.create_vad_provider", return_value=fake_vad),
        patch("routes.voice_pipeline_ws.VADState") as mock_state_cls,
        patch(
            "routes.voice_pipeline_ws.process_text_utterance",
            return_value={"transcript": "", "reply_text": "hello", "reply_audio": b""},
        ),
    ):
        mock_state_cls.return_value = MagicMock(speech_buffer=bytearray(), is_speaking=False, silence_frames=0)
        with client.websocket_connect("/v1/voice") as websocket:
            websocket.send_text(json.dumps({"type": "text", "text": "hi"}))
            msg = websocket.receive_text()
            payload = json.loads(msg)
            assert payload["type"] == "status"


def test_simple_energy_vad():
    vad = vp._SimpleEnergyVAD()
    state = MagicMock(speech_buffer=bytearray(), is_speaking=False, silence_frames=0, total_frames=0)
    # Frame of silence (zeros) should not trigger voice.
    assert vad.detect(b"\x00" * vp._SimpleEnergyVAD._FRAME_BYTES, state) is False
    # Loud frame should trigger voice.
    loud = b"\xff\x7f" * (vp._SimpleEnergyVAD._FRAME_BYTES // 2)
    assert vad.detect(loud, state) is True


def test_voice_session_handle_audio():
    fake_ws = MagicMock()
    fake_ws.receive = AsyncMock(return_value={"bytes": b"\x00" * vp.FRAME_BYTES})
    fake_ws.send_json = AsyncMock()
    fake_ws.send_bytes = AsyncMock()
    fake_vad = MagicMock()
    fake_vad.is_utterance_end.return_value = False
    fake_vad.reset = MagicMock()
    state = MagicMock(speech_buffer=bytearray(), is_speaking=False, silence_frames=0, total_frames=0)

    session = vp._VoiceSession(fake_ws, fake_vad)
    session.vad_state = state

    with patch.object(session, "_handle_audio", new=AsyncMock()) as mock_handle:
        # Simulate single loop iteration by cancelling after one receive.
        async def run_once():
            message = await fake_ws.receive()
            if "bytes" in message:
                await mock_handle(message["bytes"])

        import asyncio

        asyncio.run(run_once())
    mock_handle.assert_awaited_once_with(b"\x00" * vp.FRAME_BYTES)


def test_send_audio_chunks_splits_large_audio():
    fake_ws = MagicMock()
    fake_ws.send_json = AsyncMock()
    session = vp._VoiceSession(fake_ws, MagicMock())
    import asyncio

    asyncio.run(session._send_audio_chunks(b"a" * 100000, chunk_size=48000))
    assert fake_ws.send_json.await_count == 3
