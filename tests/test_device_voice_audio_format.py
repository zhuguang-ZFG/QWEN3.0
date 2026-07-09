"""Unit tests for device_voice audio format helpers."""

from __future__ import annotations

import pytest
from device_voice.audio_format import (
    DEFAULT_STREAM_PCM_FRAME_BYTES,
    ensure_wav_bytes,
    estimate_pcm_bytes,
    is_wav,
    iter_pcm_frames,
    pcm_stream_frame,
    pcm_to_wav_bytes,
    prepare_audio_for_streaming,
    prepare_pcm,
    read_wav_pcm,
    require_min_pcm_bytes,
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


def test_prepare_audio_for_streaming_raw_pcm():
    pcm = b"\x00\x00" * 20
    payload, sample_rate, fmt = prepare_audio_for_streaming(pcm)
    assert payload == pcm
    assert sample_rate == 16000
    assert fmt == "pcm"


def test_pcm_stream_frame_strips_wav():
    pcm = b"\x01\x00" * 40
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    assert pcm_stream_frame(wav) == pcm
    assert pcm_stream_frame(pcm) == pcm


def test_iter_pcm_frames_splits_by_1280():
    pcm = b"\x01" * (DEFAULT_STREAM_PCM_FRAME_BYTES * 2 + 100)
    frames = iter_pcm_frames(pcm)
    assert len(frames) == 3
    assert sum(len(frame) for frame in frames) == len(pcm)


def test_require_min_pcm_bytes_rejects_short_clip():
    pcm = b"\x00\x00" * 100
    with pytest.raises(ValueError, match="too short"):
        require_min_pcm_bytes(pcm, minimum=3200)


def test_estimate_pcm_bytes_ignores_wav_header():
    pcm = b"\x00\x00" * 2000
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    assert estimate_pcm_bytes(wav) == len(pcm)
