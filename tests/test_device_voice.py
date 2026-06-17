"""Unit tests for device_voice module — provider registration and factory functions."""

from __future__ import annotations

from unittest.mock import patch

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


class TestASRProvider:
    """Tests for ASR provider factory."""

    def test_create_funasr(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("funasr")
        from device_voice.providers.asr_funasr import FunASRProvider

        assert isinstance(provider, FunASRProvider)

    def test_create_aliyun_requires_credentials(self, monkeypatch):
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "sk")
        monkeypatch.setenv("ALIBABA_NLS_APP_KEY", "appkey")
        from device_voice.asr import create_asr_provider

        with patch("nls.token.getToken", return_value={"Token": {"Id": "token"}}):
            provider = create_asr_provider("aliyun")
        from device_voice.providers.asr_aliyun import AliyunASRProvider

        assert isinstance(provider, AliyunASRProvider)

    def test_create_doubao_requires_credentials(self, monkeypatch):
        monkeypatch.setenv("DOUBAO_ASR_APPID", "appid")
        monkeypatch.setenv("DOUBAO_ASR_ACCESS_TOKEN", "token")
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("doubao")
        from device_voice.providers.asr_doubao import DoubaoASRProvider

        assert isinstance(provider, DoubaoASRProvider)

    def test_create_whisper_returns_provider(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("whisper")
        from device_voice.providers.asr_whisper import WhisperASRProvider

        assert isinstance(provider, WhisperASRProvider)

    def test_funasr_transcribe_empty_audio(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("funasr")
        # Empty audio without model loaded → returns ""
        import asyncio

        result = asyncio.run(provider.transcribe(b""))
        assert result == ""

    def test_funasr_stream_transcribe_empty(self):
        from device_voice.asr import create_asr_provider

        provider = create_asr_provider("funasr")
        import asyncio

        async def _empty_stream():
            return
            yield  # pragma: no cover

        async def _run():
            chunks = []
            async for text in provider.stream_transcribe(_empty_stream()):
                chunks.append(text)
            return chunks

        result = asyncio.run(_run())
        assert result == []


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
        import asyncio

        result = asyncio.run(provider.synthesize(""))
        assert result == b""

    def test_edge_synthesize_whitespace_text(self):
        from device_voice.tts import create_tts_provider

        provider = create_tts_provider("edge")
        import asyncio

        result = asyncio.run(provider.synthesize("   "))
        assert result == b""

    def test_mp3_to_pcm_requires_ffmpeg(self, monkeypatch):
        from device_voice.providers import tts_edge

        monkeypatch.setattr(tts_edge, "_ffmpeg_available", lambda: False)
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            tts_edge._mp3_to_pcm(b"fake-mp3")


class TestVADProvider:
    """Tests for VAD provider and state management."""

    def test_create_silero(self):
        from device_voice.vad import create_vad_provider

        provider = create_vad_provider("silero")
        from device_voice.providers.vad_silero import SileroVADProvider

        assert isinstance(provider, SileroVADProvider)

    def test_vad_state_defaults(self):
        from device_voice.vad import VADState

        state = VADState()
        assert state.is_speaking is False
        assert len(state.speech_buffer) == 0
        assert state.silence_frames == 0

    def test_silero_detect_empty_without_model(self, monkeypatch):
        """SileroVAD without ONNX model must raise, not silently pass-through."""
        monkeypatch.setenv("LIMA_VOICE_MODEL_DIR", "/nonexistent/path")
        from device_voice.vad import create_vad_provider, VADModelUnavailableError, VADState

        provider = create_vad_provider("silero")
        state = VADState()
        fake_pcm = b"\x00\x00" * 512  # 512 samples of silence
        with pytest.raises(VADModelUnavailableError):
            provider.detect(fake_pcm, state)

    def test_vad_reset_clears_state(self):
        from device_voice.vad import VADState
        from device_voice.providers.vad_silero import SileroVADProvider

        state = VADState(is_speaking=True, silence_frames=100)
        state.speech_buffer.extend(b"test")
        provider = SileroVADProvider()
        provider.reset(state)
        assert state.is_speaking is False
        assert len(state.speech_buffer) == 0
        assert state.silence_frames == 0


class TestAudioStream:
    """Tests for audio_stream.py PCM helpers."""

    def test_wav_header_length(self):
        from device_voice.audio_stream import pcm_to_wav_header

        header = pcm_to_wav_header(0)
        assert len(header) == 44
        assert header[:4] == b"RIFF"
        assert header[8:12] == b"WAVE"

    def test_wav_header_zero_pcm(self):
        from device_voice.audio_stream import pcm_to_wav_header

        header = pcm_to_wav_header(0)
        import struct

        # RIFF size = 36 + 0 = 36
        assert struct.unpack("<I", header[4:8])[0] == 36

    def test_wav_header_positive_pcm(self):
        from device_voice.audio_stream import pcm_to_wav_header

        pcm_length = 16000 * 2 * 2  # 2 seconds @ 16kHz mono
        header = pcm_to_wav_header(pcm_length)
        import struct

        riff_size = struct.unpack("<I", header[4:8])[0]
        assert riff_size == 36 + pcm_length

    def test_pcm_to_wav(self):
        from device_voice.audio_stream import pcm_to_wav

        pcm = b"\x00\x00" * 16000  # 1 second @ 16kHz
        wav = pcm_to_wav(pcm)
        assert len(wav) == 44 + len(pcm)
        assert wav[:4] == b"RIFF"

    def test_estimate_duration(self):
        from device_voice.audio_stream import estimate_duration_ms, AudioConfig

        cfg = AudioConfig(sample_rate=16000)
        # 32000 bytes = 1 second at 16kHz 16-bit mono
        ms = estimate_duration_ms(32000, cfg)
        assert ms == pytest.approx(1000.0, rel=0.01)

    def test_audio_config_defaults(self):
        from device_voice.audio_stream import AudioConfig, DEFAULT_SAMPLE_RATE

        cfg = AudioConfig()
        assert cfg.sample_rate == DEFAULT_SAMPLE_RATE
        assert cfg.channels == 1
        assert cfg.sample_width == 2


class TestVoiceprintProvider:
    """Tests for voiceprint.py stub."""

    def test_speaker_identity_defaults(self):
        from device_voice.voiceprint import SpeakerIdentity

        sid = SpeakerIdentity()
        assert sid.member_id == ""
        assert sid.is_known is False
        assert sid.confidence == 0.0

    def test_identify_speaker_without_model(self):
        from device_voice.voiceprint import VoiceprintProvider
        import asyncio

        provider = VoiceprintProvider()
        result = asyncio.run(provider.identify_speaker(b"", "dev-1"))
        assert result.member_id == ""
        assert result.is_known is False
        assert result.reason == "extraction_failed"
