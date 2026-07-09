"""Tests for device_voice ASR provider registry."""

from __future__ import annotations

import pytest
from dataclasses import replace

from config.voice_settings import VOICE
from device_voice.providers.base import AsrNotConfiguredError
from device_voice.providers.funasr_local import FunAsrLocalProvider, strip_funasr_tags
from device_voice.providers.registry import create_asr_provider, supported_asr_providers


def test_supported_asr_providers():
    assert supported_asr_providers() == ("dashscope", "funasr", "whisper")


def test_create_unknown_provider_raises():
    with pytest.raises(AsrNotConfiguredError, match="unsupported"):
        create_asr_provider("unknown-provider")


def test_create_dashscope_without_api_key(monkeypatch):
    monkeypatch.setenv("LIMA_VOICE_ENABLED", "1")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("ALIYUN_API_KEY", raising=False)
    with pytest.raises(AsrNotConfiguredError, match="API key"):
        create_asr_provider("dashscope")


def test_create_dashscope_oneshot_provider(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    provider = create_asr_provider("dashscope")
    assert provider.__class__.__name__ == "Qwen3AsrFlashProvider"


def test_create_dashscope_stream_provider(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_ASR_MODEL", "paraformer-realtime-v2")
    provider = create_asr_provider("dashscope")
    assert provider.__class__.__name__ == "DashScopeRecognitionProvider"


def test_create_funasr_without_model_dir(monkeypatch):
    monkeypatch.setattr(
        "device_voice.providers.registry.VOICE",
        replace(VOICE, model_dir=""),
    )
    provider = create_asr_provider("funasr")
    with pytest.raises(AsrNotConfiguredError, match="MODEL_DIR"):
        provider._load_model()


def test_create_funasr_without_package(monkeypatch):
    monkeypatch.setattr(
        "device_voice.providers.registry.VOICE",
        replace(VOICE, model_dir="data/voice_models/SenseVoiceSmall"),
    )
    provider = create_asr_provider("funasr")

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "funasr":
            raise ImportError("no funasr")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(AsrNotConfiguredError, match="funasr package"):
        provider._load_model()


@pytest.mark.asyncio
async def test_funasr_provider_transcribe_with_mock_model(monkeypatch):
    from device_voice.audio_format import pcm_to_wav_bytes

    class FakeModel:
        def generate(self, **_kwargs):
            return [{"text": "<|zh|><|Speech|>你好"}]

    provider = FunAsrLocalProvider(model_dir="models/test")
    provider._model = FakeModel()
    text = await provider.transcribe(pcm_to_wav_bytes(b"\x00\x00" * 40, sample_rate=16000))
    assert text == "你好"


def test_strip_funasr_tags():
    assert strip_funasr_tags("<|zh|><|Speech|>画一只猫") == "画一只猫"


def test_create_whisper_without_package(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "base")
    provider = create_asr_provider("whisper")

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("no faster_whisper")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(AsrNotConfiguredError, match="faster-whisper"):
        provider._load_model()


@pytest.mark.asyncio
async def test_whisper_provider_transcribe_with_mock_model(monkeypatch):
    from device_voice.audio_format import pcm_to_wav_bytes

    class FakeSegment:
        def __init__(self, text: str):
            self.text = text

    class FakeModel:
        def transcribe(self, _path, *, language=None):
            return [FakeSegment("你好")], None

    provider = __import__(
        "device_voice.providers.whisper_local",
        fromlist=["WhisperLocalProvider"],
    ).WhisperLocalProvider(model="base")
    provider._model = FakeModel()
    text = await provider.transcribe(pcm_to_wav_bytes(b"\x00\x00" * 40, sample_rate=16000))
    assert text == "你好"
