"""Tests for device_voice streaming ASR session selection."""

from __future__ import annotations

from dataclasses import replace

import pytest

from config.voice_settings import VOICE, VOICE_PROVIDERS
from device_voice.streaming_asr import BufferedVoiceStreamSession, DashScopeLiveStreamSession, dashscope_stream_model


def test_dashscope_stream_model_defaults_buffered():
    assert dashscope_stream_model() is None


def test_dashscope_stream_model_honors_explicit_env(monkeypatch):
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE_PROVIDERS",
        replace(
            VOICE_PROVIDERS,
            dashscope_asr=replace(VOICE_PROVIDERS.dashscope_asr, stream_model="custom-stream", model=""),
        ),
    )
    assert dashscope_stream_model() == "custom-stream"


@pytest.mark.asyncio
async def test_open_voice_stream_session_buffered_by_default(monkeypatch):
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE",
        replace(VOICE, enabled=True, asr_provider="dashscope"),
    )
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE_PROVIDERS",
        replace(VOICE_PROVIDERS, dashscope_asr=replace(VOICE_PROVIDERS.dashscope_asr, api_key="test-key")),
    )
    monkeypatch.setattr("device_voice.streaming_asr.ALIYUN_API_KEY", "")
    monkeypatch.setattr("device_voice.streaming_asr.get_asr_provider", lambda: object())
    from device_voice.streaming_asr import open_voice_stream_session

    session = await open_voice_stream_session()
    assert isinstance(session, BufferedVoiceStreamSession)


@pytest.mark.asyncio
async def test_open_voice_stream_session_uses_paraformer_when_configured(monkeypatch):
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE",
        replace(VOICE, enabled=True, asr_provider="dashscope"),
    )
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE_PROVIDERS",
        replace(
            VOICE_PROVIDERS,
            dashscope_asr=replace(
                VOICE_PROVIDERS.dashscope_asr,
                api_key="test-key",
                stream_model="paraformer-realtime-v2",
            ),
        ),
    )
    monkeypatch.setattr("device_voice.streaming_asr.ALIYUN_API_KEY", "")
    from device_voice.streaming_asr import open_voice_stream_session

    session = await open_voice_stream_session()
    assert isinstance(session, DashScopeLiveStreamSession)


@pytest.mark.asyncio
async def test_open_voice_stream_session_buffered_for_whisper(monkeypatch):
    monkeypatch.setenv("LIMA_VOICE_ENABLED", "1")
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE",
        replace(VOICE, enabled=True, asr_provider="whisper"),
    )
    monkeypatch.setattr(
        "device_voice.streaming_asr.get_asr_provider",
        lambda: object(),
    )
    from device_voice.streaming_asr import open_voice_stream_session

    session = await open_voice_stream_session()
    assert isinstance(session, BufferedVoiceStreamSession)


@pytest.mark.asyncio
async def test_buffered_session_rejects_oversized_feed(monkeypatch):
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE",
        replace(VOICE, max_audio_bytes=32),
    )
    session = BufferedVoiceStreamSession()
    await session.feed(b"\x00\x01" * 8)
    with pytest.raises(ValueError, match="exceeds max size"):
        await session.feed(b"\x00\x01" * 10)


@pytest.mark.asyncio
async def test_dashscope_feed_splits_frames_and_paces(monkeypatch):
    monkeypatch.setattr(
        "device_voice.streaming_asr.VOICE",
        replace(VOICE, stream_pcm_frame_bytes=160, stream_frame_interval_ms=10, max_audio_bytes=4096),
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    fed: list[bytes] = []
    session = DashScopeLiveStreamSession(api_key="k", model="paraformer-realtime-v2")
    session._started = True
    session._feed_sync = lambda frame: fed.append(frame)  # type: ignore[method-assign]
    monkeypatch.setattr("device_voice.streaming_asr.asyncio.sleep", fake_sleep)

    await session.feed(b"\x00\x01" * 160)
    assert len(fed) == 2
    assert all(len(frame) == 160 for frame in fed)
    assert sleeps == [0.01]


@pytest.mark.asyncio
async def test_dashscope_close_stops_recognition(monkeypatch):
    stopped: list[str] = []

    class FakeRecognition:
        def stop(self) -> None:
            stopped.append("stop")

    session = DashScopeLiveStreamSession(api_key="k", model="paraformer-realtime-v2")
    session._started = True
    session._recognition = FakeRecognition()
    session._done = __import__("threading").Event()

    await session.close()
    assert stopped == ["stop"]
    assert session._started is False
    assert session._recognition is None
