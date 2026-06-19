"""Unit tests for Aliyun NLS ASR provider."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from device_voice.exceptions import AuthenticationError, ConfigurationError


class TestAliyunASRProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)
        monkeypatch.delenv("ALIBABA_NLS_APP_KEY", raising=False)

        from device_voice.providers.asr_aliyun import AliyunASRProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            AliyunASRProvider()

    def test_transcribe_success(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.asr_aliyun import AliyunASRProvider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token123"}}):
            provider = AliyunASRProvider()

        captured_callbacks: dict = {}

        def _make_recognizer(*_args, **kwargs):
            captured_callbacks.update(kwargs)
            mock_recognizer = MagicMock()

            def _start(**_start_kwargs):
                # Simulate recognition completing immediately.
                on_completed = captured_callbacks.get("on_completed")
                if on_completed:
                    on_completed('{"payload":{"result":"你好"}}')

            mock_recognizer.start = _start
            mock_recognizer.send_audio = MagicMock()
            mock_recognizer.stop = MagicMock()
            mock_recognizer.shutdown = MagicMock()
            return mock_recognizer

        with patch("nls.NlsSpeechRecognizer", side_effect=_make_recognizer):
            result = asyncio.run(provider.transcribe(b"fake pcm"))
        assert result == "你好"

    def test_transcribe_auth_failure(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.asr_aliyun import AliyunASRProvider
        from device_voice.exceptions import AuthenticationError

        with patch("nls.token.getToken", side_effect=Exception("invalid key")):
            with pytest.raises(AuthenticationError):
                AliyunASRProvider()

    def test_transcribe_success_string_token(self, monkeypatch):
        """The real NLS SDK may return the token as a plain string."""
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.asr_aliyun import AliyunASRProvider

        with patch("nls.token.getToken", return_value="token123"):
            provider = AliyunASRProvider()

        captured_callbacks: dict = {}

        def _make_recognizer(*_args, **kwargs):
            captured_callbacks.update(kwargs)
            mock_recognizer = MagicMock()

            def _start(**_start_kwargs):
                on_completed = captured_callbacks.get("on_completed")
                if on_completed:
                    on_completed('{"payload":{"result":"你好"}}')

            mock_recognizer.start = _start
            mock_recognizer.send_audio = MagicMock()
            mock_recognizer.stop = MagicMock()
            mock_recognizer.shutdown = MagicMock()
            return mock_recognizer

        with patch("nls.NlsSpeechRecognizer", side_effect=_make_recognizer):
            result = asyncio.run(provider.transcribe(b"fake pcm"))
        assert result == "你好"
