"""Audio stream helpers for WebSocket binary frame handling.

Manages PCM audio buffering between the device gateway WebSocket and the
voice pipeline (VAD → ASR → dialogue → TTS → audio reply).
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass

_log = logging.getLogger(__name__)

# Audio format constants (match xiaozhi-server / ESP32 I2S defaults)
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_SAMPLE_WIDTH = 2  # 16-bit
DEFAULT_CHANNELS = 1  # mono
BYTES_PER_SAMPLE = DEFAULT_SAMPLE_WIDTH * DEFAULT_CHANNELS

# Typical chunk size from ESP32 I2S: 512 samples = 1024 bytes
DEFAULT_CHUNK_SAMPLES = 512
DEFAULT_CHUNK_BYTES = DEFAULT_CHUNK_SAMPLES * BYTES_PER_SAMPLE

# Silence duration (ms) before considering utterance end
DEFAULT_SILENCE_THRESHOLD_MS = 1200


@dataclass
class AudioConfig:
    """Audio stream configuration. Defaults match ESP32 I2S output."""

    sample_rate: int = DEFAULT_SAMPLE_RATE
    sample_width: int = DEFAULT_SAMPLE_WIDTH
    channels: int = DEFAULT_CHANNELS
    silence_threshold_ms: int = DEFAULT_SILENCE_THRESHOLD_MS

    @property
    def bytes_per_second(self) -> int:
        return self.sample_rate * self.sample_width * self.channels


def pcm_to_wav_header(pcm_length: int, config: AudioConfig | None = None) -> bytes:
    """Build a WAV file header for the given PCM data length."""
    cfg = config or AudioConfig()
    byte_rate = cfg.sample_rate * cfg.sample_width * cfg.channels
    block_align = cfg.sample_width * cfg.channels
    # RIFF header (44 bytes total)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + pcm_length)  # file size - 8
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)  # fmt chunk size
        + struct.pack("<H", 1)  # PCM format
        + struct.pack("<H", cfg.channels)
        + struct.pack("<I", cfg.sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", cfg.sample_width * 8)  # bits per sample
        + b"data"
        + struct.pack("<I", pcm_length)
    )


def pcm_to_wav(pcm_data: bytes, config: AudioConfig | None = None) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    header = pcm_to_wav_header(len(pcm_data), config)
    return header + pcm_data


def estimate_duration_ms(pcm_bytes: int, config: AudioConfig | None = None) -> float:
    """Estimate audio duration in milliseconds from PCM byte count."""
    cfg = config or AudioConfig()
    return (pcm_bytes / cfg.bytes_per_second) * 1000.0
