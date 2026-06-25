"""Tests for routes/device_voice_ws_helpers.py."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes import device_voice_ws_helpers as dvh


def test_decode_limited_audio_success():
    data = base64.b64encode(b"pcm-data").decode()
    assert dvh._decode_limited_audio(data, "dev-1", "audio") == b"pcm-data"


def test_decode_limited_audio_invalid_base64():
    assert dvh._decode_limited_audio("not-b64!!!", "dev-1", "audio") is None


def test_decode_limited_audio_enforces_size_limit(monkeypatch):
    monkeypatch.setattr(dvh, "_MAX_AUDIO_BYTES", 4)
    data = base64.b64encode(b"pcm-data").decode()
    assert dvh._decode_limited_audio(data, "dev-1", "audio") is None


@pytest.mark.asyncio
async def test_handle_audio_chunk_invalid_data():
    websocket = MagicMock()
    result = await dvh.handle_audio_chunk(websocket, "dev-1", {"data": "bad-b64"}, "req-1")
    assert result is True


@pytest.mark.asyncio
async def test_handle_audio_chunk_valid_data():
    with patch.object(dvh, "_feed_audio_to_pipeline") as mock_feed:
        data = base64.b64encode(b"pcm").decode()
        result = await dvh.handle_audio_chunk(
            websocket := MagicMock(), "dev-1", {"data": data, "is_end": True}, "req-1"
        )
    assert result is True
    mock_feed.assert_awaited_once()


def test_get_vad_state_initializes(monkeypatch):
    fake_state = MagicMock()
    fake_provider = MagicMock()
    with (
        patch("device_voice.vad.VADState", return_value=fake_state),
        patch("device_voice.get_vad_provider", return_value=fake_provider),
    ):
        state_pair = dvh._get_vad_state("dev-1")
    assert state_pair == (fake_state, fake_provider)
    assert "dev-1" in dvh._audio_registry
    dvh._audio_registry.clear()


def test_get_vad_state_unavailable():
    orig_import = __builtins__["__import__"]

    def _raising_import(name, *args, **kwargs):
        if name == "device_voice.vad":
            raise ImportError("no vad")
        return orig_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_raising_import):
        assert dvh._get_vad_state("dev-1") is None


@pytest.mark.asyncio
async def test_detect_utterance_returns_true():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    vad_state = MagicMock()
    vad_state.speech_buffer = [b"data"]
    vad_provider = MagicMock()
    with patch("device_voice.vad.VADModelUnavailableError", RuntimeError):
        result = await dvh._detect_utterance(websocket, "dev-1", b"chunk", vad_state, vad_provider)
    assert result is True
    vad_provider.detect.assert_called_once_with(b"chunk", vad_state)


@pytest.mark.asyncio
async def test_detect_utterance_model_unavailable():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    vad_state = MagicMock()
    vad_provider = MagicMock()
    vad_provider.detect.side_effect = RuntimeError("model unavailable")
    with patch("device_voice.vad.VADModelUnavailableError", RuntimeError):
        result = await dvh._detect_utterance(websocket, "dev-1", b"chunk", vad_state, vad_provider)
    assert result is False
    websocket.send_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_utterance_success():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    websocket.send_bytes = AsyncMock()
    with (
        patch(
            "device_voice.dialogue.process_voice_utterance",
            return_value={
                "transcript": "hello",
                "reply_audio": b"audio",
                "voiceprint": {"member_id": "m1"},
            },
        ) as mock_process,
        patch("routes.device_voice_ws_helpers.shadow_store") as mock_shadow,
    ):
        await dvh._process_utterance(websocket, "dev-1", b"pcm")
    mock_process.assert_awaited_once()
    mock_shadow.update_voiceprint_result.assert_called_once_with("dev-1", {"member_id": "m1"})


@pytest.mark.asyncio
async def test_process_utterance_exception_goes_idle():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    with patch("device_voice.dialogue.process_voice_utterance", side_effect=RuntimeError("boom")):
        await dvh._process_utterance(websocket, "dev-1", b"pcm")
    last_call = websocket.send_json.await_args_list[-1]
    assert last_call.args[0]["status"] == "idle"


@pytest.mark.asyncio
async def test_feed_audio_to_pipeline_voice_disabled():
    websocket = MagicMock()
    with patch("device_voice.VOICE_ENABLED", False):
        await dvh._feed_audio_to_pipeline(websocket, "dev-1", b"chunk")
    websocket.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_feed_audio_to_pipeline_utterance_end():
    websocket = MagicMock()
    vad_state = MagicMock()
    vad_state.speech_buffer = bytearray(b"utterance")
    vad_provider = MagicMock()
    vad_provider.is_utterance_end.return_value = True
    dvh._audio_registry["dev-1"] = (vad_state, vad_provider)
    with (
        patch("device_voice.VOICE_ENABLED", True),
        patch.object(dvh, "_process_utterance", new=AsyncMock()) as mock_process,
    ):
        await dvh._feed_audio_to_pipeline(websocket, "dev-1", b"chunk")
    vad_provider.reset.assert_called_once_with(vad_state)
    mock_process.assert_awaited_once_with(websocket, "dev-1", b"utterance")
    dvh._audio_registry.clear()


def test_cleanup_audio_registry():
    dvh._audio_registry["dev-1"] = (MagicMock(), MagicMock())
    dvh._cleanup_audio_registry("dev-1")
    assert "dev-1" not in dvh._audio_registry


def test_ensure_wav_already_wav():
    assert dvh._ensure_wav(b"wav-data", "wav") == b"wav-data"


def test_ensure_wav_pcm_to_wav():
    fake_config = MagicMock()
    with patch.object(dvh, "pcm_to_wav", return_value=b"wav-converted") as mock_conv:
        result = dvh._ensure_wav(b"pcm-data", "raw_pcm", config=fake_config)
    assert result == b"wav-converted"
    mock_conv.assert_called_once_with(b"pcm-data", fake_config)


def test_ensure_wav_unsupported_format():
    assert dvh._ensure_wav(b"data", "mp3") is None


@pytest.mark.asyncio
async def test_extract_and_store_voiceprint_embedding_success():
    validated = {"audio_data": base64.b64encode(b"wav-audio").decode(), "format": "wav"}
    provider = MagicMock()
    provider.enabled = True
    provider.register_speaker = AsyncMock(return_value=[0.1, 0.2])
    provider.invalidate_cache = AsyncMock()
    with (
        patch("device_voice.VOICE_ENABLED", True),
        patch("device_voice.voiceprint.get_voiceprint_provider", return_value=provider),
        patch("session_memory.store_voiceprint.store_voiceprint_embedding") as mock_store,
    ):
        await dvh._extract_and_store_voiceprint_embedding(validated, "vp-1", "member-1", "dev-1")
    provider.register_speaker.assert_awaited_once_with(b"wav-audio", "member-1", "dev-1")
    mock_store.assert_called_once()
    provider.invalidate_cache.assert_awaited_once_with("dev-1")


@pytest.mark.asyncio
async def test_extract_and_store_voiceprint_embedding_provider_disabled():
    validated = {"audio_data": base64.b64encode(b"wav-audio").decode(), "format": "wav"}
    provider = MagicMock()
    provider.enabled = False
    with (
        patch("device_voice.VOICE_ENABLED", True),
        patch("device_voice.voiceprint.get_voiceprint_provider", return_value=provider),
    ):
        await dvh._extract_and_store_voiceprint_embedding(validated, "vp-1", "member-1", "dev-1")
    provider.register_speaker.assert_not_called()
