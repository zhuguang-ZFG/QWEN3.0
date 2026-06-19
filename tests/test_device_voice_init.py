"""Unit tests for device_voice module initialization and factory functions."""

from __future__ import annotations

import pytest


class TestDeviceVoiceInit:
    """Tests for device_voice.__init__ module-level config and lazy loading."""

    def test_voice_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("LIMA_VOICE_ENABLED", raising=False)
        from device_voice import VOICE_ENABLED

        assert VOICE_ENABLED is False

    def test_voice_enabled_flag(self, monkeypatch):
        monkeypatch.setenv("LIMA_VOICE_ENABLED", "1")
        from importlib import reload
        import device_voice.__init__ as dv

        reload(dv)
        assert dv.VOICE_ENABLED is True

    def test_default_provider_names(self):
        import device_voice

        assert device_voice.ASR_PROVIDER == "funasr"
        assert device_voice.TTS_PROVIDER == "edge"
        assert device_voice.VAD_PROVIDER == "silero"

    def test_get_asr_provider_returns_funasr(self):
        from device_voice import get_asr_provider

        provider = get_asr_provider()
        assert provider is not None
        from device_voice.providers.asr_funasr import FunASRProvider

        assert isinstance(provider, FunASRProvider)

    def test_get_tts_provider_returns_edge(self):
        from device_voice import get_tts_provider

        provider = get_tts_provider()
        assert provider is not None
        from device_voice.providers.tts_edge import EdgeTTSProvider

        assert isinstance(provider, EdgeTTSProvider)

    def test_get_vad_provider_returns_silero(self):
        from device_voice import get_vad_provider

        provider = get_vad_provider()
        assert provider is not None
        from device_voice.providers.vad_silero import SileroVADProvider

        assert isinstance(provider, SileroVADProvider)

    def test_get_asr_provider_singleton(self):
        from device_voice import get_asr_provider

        p1 = get_asr_provider()
        p2 = get_asr_provider()
        assert p1 is p2

    def test_fallback_on_unknown_provider(self, monkeypatch):
        monkeypatch.setenv("LIMA_VOICE_ASR_PROVIDER", "nonexistent")
        from importlib import reload
        import device_voice.__init__ as dv

        reload(dv)
        provider = dv.get_asr_provider()
        from device_voice.providers.asr_funasr import FunASRProvider

        assert isinstance(provider, FunASRProvider)
