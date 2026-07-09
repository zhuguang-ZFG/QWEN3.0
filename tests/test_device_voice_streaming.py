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
