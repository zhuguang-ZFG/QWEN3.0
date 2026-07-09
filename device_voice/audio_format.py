"""Audio format helpers for device-app voice transcribe."""

from __future__ import annotations

import io
import wave

_SUPPORTED_SAMPLE_RATES = frozenset({8000, 16000})
_DEFAULT_PCM_SAMPLE_RATE = 16000
# 16 kHz mono 16-bit: 32000 bytes/s; 1280 bytes ≈ 40 ms (DCloud Voice2Text / 设计文档 frameSize).
DEFAULT_STREAM_PCM_FRAME_BYTES = 1280


def content_type_for_audio(audio_data: bytes) -> str:
    if len(audio_data) >= 4 and audio_data[:4] == b"RIFF":
        return "audio/wav"
    return "audio/L16"


def is_wav(audio_data: bytes) -> bool:
    return len(audio_data) >= 12 and audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE"


def pcm_to_wav_bytes(pcm_data: bytes, *, sample_rate: int = 16000) -> bytes:
    """Wrap mono 16-bit PCM in a WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buffer.getvalue()


def read_wav_pcm(audio_data: bytes) -> tuple[bytes, int]:
    """Parse a WAV blob and return mono PCM frames plus sample rate."""
    with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        if channels != 1:
            raise ValueError("only mono audio is supported")
        if sample_width != 2:
            raise ValueError("only 16-bit audio is supported")
        if sample_rate not in _SUPPORTED_SAMPLE_RATES:
            raise ValueError("unsupported sample rate; use 8000 or 16000 Hz")
        pcm_data = wav_file.readframes(wav_file.getnframes())
    if not pcm_data:
        raise ValueError("audio payload is empty")
    return pcm_data, sample_rate


def ensure_wav_bytes(audio_data: bytes, *, sample_rate: int = 16000) -> bytes:
    """Return WAV bytes suitable for one-shot ASR file upload."""
    if is_wav(audio_data):
        read_wav_pcm(audio_data)
        return audio_data
    if not audio_data:
        raise ValueError("audio payload is empty")
    return pcm_to_wav_bytes(audio_data, sample_rate=sample_rate)


def prepare_audio_for_streaming(audio_data: bytes) -> tuple[bytes, int, str]:
    """Return payload, sample rate, and DashScope format for streaming ASR."""
    if is_wav(audio_data):
        _pcm_data, sample_rate = read_wav_pcm(audio_data)
        return audio_data, sample_rate, "wav"
    if not audio_data:
        raise ValueError("audio payload is empty")
    return audio_data, _DEFAULT_PCM_SAMPLE_RATE, "pcm"


def pcm_stream_frame(chunk: bytes) -> bytes:
    """Normalize one WS audio frame to raw PCM (strip accidental WAV wrapper)."""
    if not chunk:
        return b""
    if is_wav(chunk):
        pcm_data, _sample_rate = read_wav_pcm(chunk)
        return pcm_data
    return chunk


def estimate_pcm_bytes(audio_data: bytes) -> int:
    """Return mono PCM payload length (strip WAV container when present)."""
    if not audio_data:
        return 0
    if is_wav(audio_data):
        pcm_data, _sample_rate = read_wav_pcm(audio_data)
        return len(pcm_data)
    return len(audio_data)


def require_min_pcm_bytes(audio_data: bytes, *, minimum: int) -> None:
    """Reject clips shorter than *minimum* PCM bytes (~100 ms at 16 kHz by default)."""
    pcm_len = estimate_pcm_bytes(audio_data)
    if pcm_len < minimum:
        raise ValueError(f"audio is too short ({pcm_len} bytes PCM; need at least {minimum})")


def iter_pcm_frames(pcm_data: bytes, *, frame_bytes: int = DEFAULT_STREAM_PCM_FRAME_BYTES) -> list[bytes]:
    """Split PCM into fixed-size frames for realtime ASR (Aliyun: send near real-time, not in one burst)."""
    if not pcm_data:
        return []
    size = max(160, frame_bytes)
    return [pcm_data[offset : offset + size] for offset in range(0, len(pcm_data), size)]


def prepare_pcm(audio_data: bytes) -> tuple[bytes, int]:
    """Backward-compatible PCM extractor for tests and legacy callers."""
    payload, sample_rate, fmt = prepare_audio_for_streaming(audio_data)
    if fmt == "wav":
        return read_wav_pcm(payload)
    return payload, sample_rate
