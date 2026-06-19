"""Unit tests for Doubao TTS provider."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from device_voice.exceptions import AuthenticationError, ConfigurationError


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
