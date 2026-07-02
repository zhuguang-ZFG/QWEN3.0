"""Unit tests for MiMo TTS provider."""

from __future__ import annotations

import base64
import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_wav_bytes(pcm: bytes, sample_rate: int = 24000) -> bytes:
    """Build a minimal WAV file from raw PCM s16le mono bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


class TestMiMoTTSProvider:
    def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.delenv("MIMO_API_KEY", raising=False)

        from device_voice.providers.tts_mimo import MiMoTTSProvider
        from device_voice.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            MiMoTTSProvider()

    @pytest.mark.asyncio
    async def test_synthesize_success(self, monkeypatch):
        monkeypatch.setenv("MIMO_API_KEY", "sk-test")

        from device_voice.providers.tts_mimo import MiMoTTSProvider

        provider = MiMoTTSProvider()
        pcm = b"\x01\x02" * 480  # 480 samples @ 24kHz
        wav = _make_wav_bytes(pcm)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": base64.b64encode(wav).decode("ascii")}}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.synthesize("你好", sample_rate=24000)

        assert result == pcm

    @pytest.mark.asyncio
    async def test_synthesize_auth_failure(self, monkeypatch):
        monkeypatch.setenv("MIMO_API_KEY", "sk-test")

        from device_voice.providers.tts_mimo import MiMoTTSProvider
        from device_voice.exceptions import AuthenticationError

        provider = MiMoTTSProvider()

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

    @pytest.mark.asyncio
    async def test_synthesize_http_error(self, monkeypatch):
        monkeypatch.setenv("MIMO_API_KEY", "sk-test")

        from device_voice.providers.tts_mimo import MiMoTTSProvider
        from device_voice.exceptions import VoiceProviderError

        provider = MiMoTTSProvider()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(VoiceProviderError):
                await provider.synthesize("你好")
