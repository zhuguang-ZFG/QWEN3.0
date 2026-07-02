"""Unit tests for Aliyun NLS TTS provider."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestAliyunTTSProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIYUN_AK_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)
        monkeypatch.delenv("ALIYUN_AK_SECRET", raising=False)
        monkeypatch.delenv("ALIBABA_NLS_APP_KEY", raising=False)

        from device_voice.providers.tts_aliyun import AliyunTTSProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            AliyunTTSProvider()

    def test_credentials_accept_ak_aliases(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)
        monkeypatch.setenv("ALIYUN_AK_ID", "ak-alias")
        monkeypatch.setenv("ALIYUN_AK_SECRET", "sk-alias")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token123"}}):
            provider = AliyunTTSProvider()

        assert provider._ak_id == "ak-alias"
        assert provider._ak_secret == "sk-alias"

    def test_synthesize_empty_text(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token123"}}):
            provider = AliyunTTSProvider()
        result = asyncio.run(provider.synthesize(""))
        assert result == b""

    def test_synthesize_success(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token123"}}):
            provider = AliyunTTSProvider()

        captured_callbacks: dict = {}

        def _make_synthesizer(*_args, **kwargs):
            captured_callbacks.update(kwargs)
            mock_synthesizer = MagicMock()

            def _start(**_start_kwargs):
                on_data = captured_callbacks.get("on_data")
                if on_data:
                    on_data(b"pcm_data")
                on_completed = captured_callbacks.get("on_completed")
                if on_completed:
                    on_completed('{"payload":{}}')

            mock_synthesizer.start = _start
            mock_synthesizer.shutdown = MagicMock()
            return mock_synthesizer

        with patch("nls.NlsSpeechSynthesizer", side_effect=_make_synthesizer):
            result = asyncio.run(provider.synthesize("你好"))
        assert result == b"pcm_data"

    def test_synthesize_auth_failure(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider
        from device_voice.exceptions import AuthenticationError

        with patch("nls.token.getToken", side_effect=Exception("invalid key")):
            with pytest.raises(AuthenticationError):
                AliyunTTSProvider()

    def test_synthesize_success_string_token(self, monkeypatch):
        """The real NLS SDK may return the token as a plain string."""
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider

        with patch("nls.token.getToken", return_value="token123"):
            provider = AliyunTTSProvider()

        captured_callbacks: dict = {}

        def _make_synthesizer(*_args, **kwargs):
            captured_callbacks.update(kwargs)
            mock_synthesizer = MagicMock()

            def _start(**_start_kwargs):
                on_data = captured_callbacks.get("on_data")
                if on_data:
                    on_data(b"pcm_data")
                on_completed = captured_callbacks.get("on_completed")
                if on_completed:
                    on_completed('{"payload":{}}')

            mock_synthesizer.start = _start
            mock_synthesizer.shutdown = MagicMock()
            return mock_synthesizer

        with patch("nls.NlsSpeechSynthesizer", side_effect=_make_synthesizer):
            result = asyncio.run(provider.synthesize("你好"))
        assert result == b"pcm_data"
