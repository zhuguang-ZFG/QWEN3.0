"""Unit tests for Doubao ASR provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from device_voice.exceptions import AuthenticationError, ConfigurationError


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

        with (
            patch("websockets.connect", return_value=mock_ws),
            patch("device_voice.providers.asr_doubao.parse_response", side_effect=_parse_response),
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
