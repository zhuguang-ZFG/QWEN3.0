"""Unit tests for DashScope TTS provider."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from device_voice.exceptions import AuthenticationError, ConfigurationError


class TestDashScopeTTSProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("ALIYUN_API_KEY", raising=False)

        from device_voice.providers.tts_dashscope import DashScopeTTSProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            DashScopeTTSProvider()

    def test_synthesize_empty_text(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

        from device_voice.providers.tts_dashscope import DashScopeTTSProvider

        provider = DashScopeTTSProvider()
        result = asyncio.run(provider.synthesize(""))
        assert result == b""

    def test_synthesize_success(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

        from device_voice.providers.tts_dashscope import DashScopeTTSProvider

        provider = DashScopeTTSProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_result = MagicMock()
        mock_result.get_audio_data.return_value = b"pcm_data"
        mock_result.get_response.return_value = mock_response

        with patch(
            "dashscope.audio.tts.SpeechSynthesizer.call",
            return_value=mock_result,
        ):
            result = asyncio.run(provider.synthesize("你好"))
        assert result == b"pcm_data"

    def test_synthesize_auth_failure(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

        from device_voice.providers.tts_dashscope import DashScopeTTSProvider
        from device_voice.exceptions import AuthenticationError

        provider = DashScopeTTSProvider()

        with patch(
            "dashscope.audio.tts.SpeechSynthesizer.call",
            side_effect=Exception("api key invalid"),
        ):
            with pytest.raises(AuthenticationError):
                asyncio.run(provider.synthesize("你好"))

    def test_synthesize_access_denied_response(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

        from device_voice.providers.tts_dashscope import DashScopeTTSProvider
        from device_voice.exceptions import AuthenticationError

        provider = DashScopeTTSProvider()

        mock_response = MagicMock()
        mock_response.status_code = 44
        mock_response.code = "AccessDenied"
        mock_response.message = "Access denied, please make sure your account is in good standing."

        mock_result = MagicMock()
        mock_result.get_audio_data.return_value = b""
        mock_result.get_response.return_value = mock_response

        with patch(
            "dashscope.audio.tts.SpeechSynthesizer.call",
            return_value=mock_result,
        ):
            with pytest.raises(AuthenticationError):
                asyncio.run(provider.synthesize("你好"))
