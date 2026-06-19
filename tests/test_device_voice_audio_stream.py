"""Unit tests for audio_stream.py PCM helpers."""

from __future__ import annotations

import struct

import pytest


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
        # RIFF size = 36 + 0 = 36
        assert struct.unpack("<I", header[4:8])[0] == 36

    def test_wav_header_positive_pcm(self):
        from device_voice.audio_stream import pcm_to_wav_header

        pcm_length = 16000 * 2 * 2  # 2 seconds @ 16kHz mono
        header = pcm_to_wav_header(pcm_length)
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
