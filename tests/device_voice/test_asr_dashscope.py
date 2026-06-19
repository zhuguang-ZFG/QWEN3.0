"""Unit tests for DashScope ASR provider."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from device_voice.exceptions import AuthenticationError, ConfigurationError


class TestDashScopeASRProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("ALIYUN_API_KEY", raising=False)

        from device_voice.providers.asr_dashscope import DashScopeASRProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            DashScopeASRProvider()

    def test_transcribe_success(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

        from device_voice.providers.asr_dashscope import DashScopeASRProvider

        provider = DashScopeASRProvider()

        mock_recognition = MagicMock()

        def _start(**_kwargs):
            callback = mock_recognition.callback
            callback.on_open()
            callback.on_event(MagicMock(get_sentence=lambda: {"text": "你好"}))
            callback.on_complete()

        mock_recognition.start = _start
        mock_recognition.send_audio_frame = MagicMock()
        mock_recognition.stop = MagicMock()

        def _make_recognition(*_args, **kwargs):
            mock_recognition.callback = kwargs["callback"]
            return mock_recognition

        with patch("dashscope.audio.asr.Recognition", side_effect=_make_recognition):
            result = asyncio.run(provider.transcribe(b"fake pcm"))
        assert result == "你好"

    def test_transcribe_auth_failure(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

        from device_voice.providers.asr_dashscope import DashScopeASRProvider
        from device_voice.exceptions import AuthenticationError

        provider = DashScopeASRProvider()

        with patch(
            "dashscope.audio.asr.Recognition",
            side_effect=Exception("authentication failed"),
        ):
            with pytest.raises(AuthenticationError):
                asyncio.run(provider.transcribe(b"fake pcm"))
