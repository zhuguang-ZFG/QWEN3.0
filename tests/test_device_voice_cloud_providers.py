"""Unit tests for cloud ASR/TTS providers (Aliyun NLS / Doubao).

These tests mock the external SDKs and network clients so they can run in CI
without real credentials.
"""

from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.asr_aliyun import AliyunASRProvider
        from device_voice.exceptions import AuthenticationError

        with patch("nls.token.getToken", side_effect=Exception("invalid key")):
            with pytest.raises(AuthenticationError):
                AliyunASRProvider()


class TestAliyunTTSProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)
        monkeypatch.delenv("ALIBABA_NLS_APP_KEY", raising=False)

        from device_voice.providers.tts_aliyun import AliyunTTSProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            AliyunTTSProvider()

    def test_synthesize_empty_text(self, monkeypatch):
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token123"}}):
            provider = AliyunTTSProvider()
        result = asyncio.run(provider.synthesize(""))
        assert result == b""

    def test_synthesize_success(self, monkeypatch):
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
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")

        from device_voice.providers.tts_aliyun import AliyunTTSProvider
        from device_voice.exceptions import AuthenticationError

        with patch("nls.token.getToken", side_effect=Exception("invalid key")):
            with pytest.raises(AuthenticationError):
                AliyunTTSProvider()


class TestDoubaoASRProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("DOUBAO_ASR_APPID", raising=False)
        monkeypatch.delenv("DOUBAO_ASR_ACCESS_TOKEN", raising=False)

        from device_voice.providers.asr_doubao import DoubaoASRProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            DoubaoASRProvider()

    @pytest.mark.asyncio
    async def test_transcribe_success(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_ASR_APPID", "appid")
        monkeypatch.setenv("DOUBAO_ASR_ACCESS_TOKEN", "token")

        from device_voice.providers.asr_doubao import DoubaoASRProvider

        provider = DoubaoASRProvider()

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(side_effect=[b"ack", b"final"])
        mock_ws.send = AsyncMock()
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=False)

        def _parse_response(data: bytes) -> dict:
            if data == b"ack":
                return {"payload_msg": {"code": 1000}}
            return {"payload_msg": {"code": 1000, "result": [{"text": "你好世界"}]}}

        with patch("websockets.connect", return_value=mock_ws), patch(
            "device_voice.providers.asr_doubao.parse_response", side_effect=_parse_response
        ):
            result = await provider.transcribe(b"fake pcm")

        assert result == "你好世界"

    @pytest.mark.asyncio
    async def test_transcribe_auth_failure(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_ASR_APPID", "appid")
        monkeypatch.setenv("DOUBAO_ASR_ACCESS_TOKEN", "token")

        from device_voice.providers.asr_doubao import DoubaoASRProvider
        from device_voice.exceptions import AuthenticationError

        provider = DoubaoASRProvider()

        with patch(
            "websockets.connect",
            side_effect=Exception("InvalidStatusCode(401)"),
        ):
            with pytest.raises(AuthenticationError):
                await provider.transcribe(b"fake pcm")


class TestDoubaoTTSProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("DOUBAO_TTS_APPID", raising=False)
        monkeypatch.delenv("DOUBAO_TTS_ACCESS_TOKEN", raising=False)

        from device_voice.providers.tts_doubao import DoubaoTTSProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            DoubaoTTSProvider()

    @pytest.mark.asyncio
    async def test_synthesize_success(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_TTS_APPID", "appid")
        monkeypatch.setenv("DOUBAO_TTS_ACCESS_TOKEN", "token")

        from device_voice.providers.tts_doubao import DoubaoTTSProvider

        provider = DoubaoTTSProvider()
        audio = b"fake pcm audio"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": base64.b64encode(audio).decode("ascii")}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("你好")

        assert result == audio

    @pytest.mark.asyncio
    async def test_synthesize_http_error(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_TTS_APPID", "appid")
        monkeypatch.setenv("DOUBAO_TTS_ACCESS_TOKEN", "token")

        from device_voice.providers.tts_doubao import DoubaoTTSProvider
        from device_voice.exceptions import AuthenticationError

        provider = DoubaoTTSProvider()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AuthenticationError):
                await provider.synthesize("你好")
