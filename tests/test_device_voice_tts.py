"""Unit tests for TTS provider factory."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


class TestTTSProvider:
    """Tests for TTS provider factory."""

    def test_create_edge(self):
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("edge")
        from device_voice.providers.tts_edge import EdgeTTSProvider

        assert isinstance(provider, EdgeTTSProvider)

    def test_create_doubao_requires_credentials(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_TTS_APPID", "appid")
        monkeypatch.setenv("DOUBAO_TTS_ACCESS_TOKEN", "token")
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("doubao")
        from device_voice.providers.tts_doubao import DoubaoTTSProvider

        assert isinstance(provider, DoubaoTTSProvider)

    def test_create_mimo_requires_credentials(self, monkeypatch):
        monkeypatch.setenv("MIMO_API_KEY", "sk-test")
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("mimo")
        from device_voice.providers.tts_mimo import MiMoTTSProvider

        assert isinstance(provider, MiMoTTSProvider)

    def test_create_aliyun_requires_credentials(self, monkeypatch):
        pytest.importorskip("nls")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")
        from device_voice.tts import create_tts_provider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token"}}):
            provider = create_tts_provider("aliyun")
        from device_voice.providers.tts_aliyun import AliyunTTSProvider

        assert isinstance(provider, AliyunTTSProvider)

    def test_edge_default_voice(self):
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("edge")
        assert provider.default_voice == "zh-CN-XiaoxiaoNeural"

    def test_edge_synthesize_empty_text(self):
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("edge")
        result = asyncio.run(provider.synthesize(""))
        assert result == b""

    def test_edge_synthesize_whitespace_text(self):
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("edge")
        result = asyncio.run(provider.synthesize("   "))
        assert result == b""

    def test_mp3_to_pcm_requires_ffmpeg(self, monkeypatch):
        from device_voice.providers import tts_edge

        monkeypatch.setattr(tts_edge, "_ffmpeg_available", lambda: False)
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            tts_edge._mp3_to_pcm(b"fake-mp3")
