"""Unit tests for device_voice audio format helpers."""

from __future__ import annotations

import pytest
from device_voice.audio_format import (
    ensure_wav_bytes,
    is_wav,
    pcm_to_wav_bytes,
    prepare_pcm,
    read_wav_pcm,
)


def test_pcm_to_wav_and_back():
    pcm = b"\x01\x00" * 80
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    assert is_wav(wav)
    parsed_pcm, sample_rate = read_wav_pcm(wav)
    assert sample_rate == 16000
    assert parsed_pcm == pcm


def test_prepare_pcm_strips_wav_header():
    pcm = b"\x00\x00" * 40
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    stripped, sample_rate = prepare_pcm(wav)
    assert sample_rate == 16000
    assert stripped == pcm


def test_read_wav_rejects_stereo():
    pcm = b"\x00\x00" * 40
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    # Corrupt channel count in fmt chunk (byte 22 in standard header).
    broken = bytearray(wav)
    broken[22] = 2
    with pytest.raises(ValueError, match="mono"):
        read_wav_pcm(bytes(broken))


def test_ensure_wav_bytes_wraps_raw_pcm():
    pcm = b"\x00\x00" * 20
    wav = ensure_wav_bytes(pcm, sample_rate=16000)
    assert is_wav(wav)
    assert read_wav_pcm(wav)[0] == pcm
