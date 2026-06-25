"""Tests for routes/ws_voice_transcript_helpers.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes import ws_voice_transcript_helpers as vt


def _status_frame(*args, **kwargs):
    status = args[1] if len(args) > 1 else kwargs.get("status")
    return {"status": status}


@pytest.fixture
def session():
    s = MagicMock()
    s.send_json = AsyncMock()
    s.websocket = MagicMock()
    s.websocket.send_bytes = AsyncMock()
    return s


@pytest.mark.asyncio
async def test_empty_text_returns_error(session):
    with patch("routes.ws_voice_transcript_helpers.send_ws_error") as mock_error:
        result = await vt.handle_voice_transcript(session, "dev-1", "   ", "req-1")
    assert result is True
    mock_error.assert_called_once()


@pytest.mark.asyncio
async def test_voice_disabled_returns_error(session):
    with (
        patch("routes.ws_voice_transcript_helpers._voice_enabled", return_value=False),
        patch("routes.ws_voice_transcript_helpers.send_ws_error") as mock_error,
    ):
        result = await vt.handle_voice_transcript(session, "dev-1", "hello", "req-1")
    assert result is True
    mock_error.assert_called_once()


@pytest.mark.asyncio
async def test_successful_text_reply(session):
    with (
        patch("routes.ws_voice_transcript_helpers._voice_enabled", return_value=True),
        patch("routes.ws_voice_transcript_helpers.voice_status_frame", side_effect=_status_frame),
        patch("routes.ws_voice_transcript_helpers.audio_reply_frame", return_value={"type": "audio"}),
        patch(
            "device_voice.dialogue.process_text_utterance",
            return_value={"reply_text": "hi there", "reply_audio": b"audio-data"},
        ) as mock_process,
    ):
        result = await vt.handle_voice_transcript(session, "dev-1", "hello", "req-1")
    assert result is True
    mock_process.assert_awaited_once_with("hello", "dev-1")
    assert session.send_json.await_count == 4  # thinking, speaking, audio, idle
    session.websocket.send_bytes.assert_awaited_once_with(b"audio-data")


@pytest.mark.asyncio
async def test_success_without_audio(session):
    with (
        patch("routes.ws_voice_transcript_helpers._voice_enabled", return_value=True),
        patch("routes.ws_voice_transcript_helpers.voice_status_frame", side_effect=_status_frame),
        patch(
            "device_voice.dialogue.process_text_utterance",
            return_value={"reply_text": "hi there"},
        ),
    ):
        result = await vt.handle_voice_transcript(session, "dev-1", "hello", "req-1")
    assert result is True
    session.websocket.send_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_exception_returns_idle(session):
    with (
        patch("routes.ws_voice_transcript_helpers._voice_enabled", return_value=True),
        patch("routes.ws_voice_transcript_helpers.voice_status_frame", side_effect=_status_frame),
        patch("device_voice.dialogue.process_text_utterance", side_effect=RuntimeError("boom")),
    ):
        result = await vt.handle_voice_transcript(session, "dev-1", "hello", "req-1")
    assert result is True
    # Last frame should be idle.
    last_call = session.send_json.await_args_list[-1]
    assert last_call.args[0]["status"] == "idle"
