"""Unit tests for Aliyun fallback ASR provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from device_voice.exceptions import ConfigurationError, NetworkError


class TestAliyunFallbackASRProvider:
    def test_all_missing_raises_configuration_error(self, monkeypatch):
        from device_voice.providers.asr_composite import AliyunFallbackASRProvider
        from device_voice.exceptions import ConfigurationError

        with (
            patch(
                "device_voice.providers.asr_composite.AliyunASRProvider",
                side_effect=ConfigurationError("no nls creds"),
            ),
            patch(
                "device_voice.providers.asr_composite.DashScopeASRProvider",
                side_effect=ConfigurationError("no dashscope creds"),
            ),
            patch(
                "device_voice.providers.asr_composite.WhisperASRProvider",
                side_effect=ConfigurationError("no whisper"),
            ),
        ):
            with pytest.raises(ConfigurationError):
                AliyunFallbackASRProvider()

    @pytest.mark.asyncio
    async def test_fallback_uses_first_successful_provider(self, monkeypatch):
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIYUN_AK_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)
        monkeypatch.delenv("ALIYUN_AK_SECRET", raising=False)
        monkeypatch.delenv("ALIBABA_NLS_APP_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("ALIYUN_API_KEY", raising=False)
        monkeypatch.setenv("WHISPER_MODEL", "tiny")

        from device_voice.providers.asr_composite import AliyunFallbackASRProvider
        from device_voice.exceptions import VoiceProviderError

        fake_primary = MagicMock()
        fake_primary.transcribe = AsyncMock(side_effect=VoiceProviderError("nls down"))
        fake_fallback = MagicMock()
        fake_fallback.transcribe = AsyncMock(return_value="fallback text")
        fake_whisper = MagicMock()
        fake_whisper.transcribe = AsyncMock(return_value="whisper text")

        with (
            patch(
                "device_voice.providers.asr_composite.AliyunASRProvider",
                return_value=fake_primary,
            ),
            patch(
                "device_voice.providers.asr_composite.DashScopeASRProvider",
                return_value=fake_fallback,
            ),
            patch(
                "device_voice.providers.asr_composite.WhisperASRProvider",
                return_value=fake_whisper,
            ),
        ):
            provider = AliyunFallbackASRProvider()
            result = await provider.transcribe(b"fake pcm")

        assert result == "fallback text"
        fake_primary.transcribe.assert_awaited_once()
        fake_fallback.transcribe.assert_awaited_once()
        fake_whisper.transcribe.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_primary_success_skips_fallback(self, monkeypatch):
        monkeypatch.setenv("WHISPER_MODEL", "tiny")

        from device_voice.providers.asr_composite import AliyunFallbackASRProvider

        fake_primary = MagicMock()
        fake_primary.transcribe = AsyncMock(return_value="primary text")
        fake_fallback = MagicMock()
        fake_fallback.transcribe = AsyncMock(return_value="fallback text")
        fake_whisper = MagicMock()
        fake_whisper.transcribe = AsyncMock(return_value="whisper text")

        with (
            patch(
                "device_voice.providers.asr_composite.AliyunASRProvider",
                return_value=fake_primary,
            ),
            patch(
                "device_voice.providers.asr_composite.DashScopeASRProvider",
                return_value=fake_fallback,
            ),
            patch(
                "device_voice.providers.asr_composite.WhisperASRProvider",
                return_value=fake_whisper,
            ),
        ):
            provider = AliyunFallbackASRProvider()
            result = await provider.transcribe(b"fake pcm")

        assert result == "primary text"
        fake_fallback.transcribe.assert_not_awaited()
        fake_whisper.transcribe.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_propagates_last_error_when_all_fail(self, monkeypatch):
        monkeypatch.setenv("WHISPER_MODEL", "tiny")

        from device_voice.providers.asr_composite import AliyunFallbackASRProvider
        from device_voice.exceptions import VoiceProviderError, AuthenticationError

        fake_primary = MagicMock()
        fake_primary.transcribe = AsyncMock(side_effect=VoiceProviderError("nls down"))
        fake_fallback = MagicMock()
        fake_fallback.transcribe = AsyncMock(side_effect=AuthenticationError("dashscope auth"))
        fake_whisper = MagicMock()
        fake_whisper.transcribe = AsyncMock(side_effect=NetworkError("whisper fail"))

        with (
            patch(
                "device_voice.providers.asr_composite.AliyunASRProvider",
                return_value=fake_primary,
            ),
            patch(
                "device_voice.providers.asr_composite.DashScopeASRProvider",
                return_value=fake_fallback,
            ),
            patch(
                "device_voice.providers.asr_composite.WhisperASRProvider",
                return_value=fake_whisper,
            ),
        ):
            provider = AliyunFallbackASRProvider()
            with pytest.raises(NetworkError):
                await provider.transcribe(b"fake pcm")

    @pytest.mark.asyncio
    async def test_stream_transcribe_buffers_and_yields(self, monkeypatch):
        monkeypatch.setenv("WHISPER_MODEL", "tiny")

        from device_voice.providers.asr_composite import AliyunFallbackASRProvider

        fake_primary = MagicMock()
        fake_primary.transcribe = AsyncMock(return_value="stream text")

        async def _stream():
            yield b"chunk1"
            yield b"chunk2"

        with (
            patch(
                "device_voice.providers.asr_composite.AliyunASRProvider",
                return_value=fake_primary,
            ),
            patch(
                "device_voice.providers.asr_composite.DashScopeASRProvider",
                side_effect=ConfigurationError("should not init"),
            ),
            patch(
                "device_voice.providers.asr_composite.WhisperASRProvider",
                side_effect=ConfigurationError("should not init"),
            ),
        ):
            provider = AliyunFallbackASRProvider()
            results = [text async for text in provider.stream_transcribe(_stream())]

        assert results == ["stream text"]
        fake_primary.transcribe.assert_awaited_once()
        call_args = fake_primary.transcribe.await_args
        assert call_args.kwargs.get("sample_rate") == 16000
        assert call_args.args[0] == b"chunk1chunk2"

    def test_aliyun_credentials_accept_ak_aliases(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)
        monkeypatch.setenv("ALIYUN_AK_ID", "ak-alias")
        monkeypatch.setenv("ALIYUN_AK_SECRET", "sk-alias")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.asr_aliyun import AliyunASRProvider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token123"}}):
            provider = AliyunASRProvider()

        assert provider._ak_id == "ak-alias"
        assert provider._ak_secret == "sk-alias"
