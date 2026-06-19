"""Unit tests for ASR provider factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestASRProvider:
    """Tests for ASR provider factory."""

    def test_create_funasr(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("funasr")
        from device_voice.providers.asr_funasr import FunASRProvider

        assert isinstance(provider, FunASRProvider)

    def test_create_aliyun_requires_credentials(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")
        from device_voice.asr import create_asr_provider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token"}}):
            provider = create_asr_provider("aliyun")
        from device_voice.providers.asr_aliyun import AliyunASRProvider

        assert isinstance(provider, AliyunASRProvider)

    def test_create_doubao_requires_credentials(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_ASR_APPID", "appid")
        monkeypatch.setenv("DOUBAO_ASR_ACCESS_TOKEN", "token")
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("doubao")
        from device_voice.providers.asr_doubao import DoubaoASRProvider

        assert isinstance(provider, DoubaoASRProvider)

    def test_create_whisper_returns_provider(self):
        pytest.importorskip("faster_whisper")
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("whisper")
        from device_voice.providers.asr_whisper import WhisperASRProvider

        assert isinstance(provider, WhisperASRProvider)

    def test_funasr_transcribe_empty_audio(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("funasr")
        # Empty audio without model loaded → returns ""
        import asyncio

        result = asyncio.run(provider.transcribe(b""))
        assert result == ""

    def test_funasr_stream_transcribe_empty(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("funasr")
        import asyncio

        async def _empty_stream():
            return
            yield  # pragma: no cover

        async def _run():
            chunks = []
            async for text in provider.stream_transcribe(_empty_stream()):
                chunks.append(text)
            return chunks

        result = asyncio.run(_run())
        assert result == []
