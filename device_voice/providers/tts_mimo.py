"""Xiaomi MiMo TTS provider.

Uses the MiMo OpenAI-compatible chat completions endpoint:
    POST https://api.xiaomimimo.com/v1/chat/completions

MiMo TTS returns base64-encoded audio inside the chat completion message.
This provider decodes the audio, strips the WAV container, and resamples to
the requested sample rate using ffmpeg.

Required env:
    MIMO_API_KEY

Optional env:
    MIMO_TTS_MODEL   (default: mimo-v2.5-tts)
    MIMO_TTS_VOICE   (default: default_zh)
    MIMO_TTS_FORMAT  (default: wav)

Docs: https://platform.xiaomimimo.com/docs/usage-guide/speech-synthesis-v2.5
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from typing import Any

import httpx

from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)
from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)

_BASE_URL = "https://api.xiaomimimo.com/v1"
_CHAT_URL = f"{_BASE_URL}/chat/completions"
_DEFAULT_MODEL = "mimo-v2.5-tts"
_DEFAULT_VOICE = "mimo_default"
_DEFAULT_FORMAT = "wav"


def _ffmpeg_available() -> bool:
    """Return True if ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def _decode_wav_to_pcm(wav_bytes: bytes, sample_rate: int) -> bytes:
    """Decode WAV bytes and resample to target sample_rate (s16le mono)."""
    if sample_rate == 24000:
        # MiMo WAV output is already 24kHz; strip header and return raw PCM.
        return _strip_wav_header(wav_bytes)

    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. MiMo TTS outputs 24kHz audio and must be "
            "resampled. Install ffmpeg or request sample_rate=24000."
        )

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "pipe:1",
        ],
        input=wav_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"ffmpeg WAV->PCM conversion failed: {stderr}")
    return proc.stdout


def _strip_wav_header(wav_bytes: bytes) -> bytes:
    """Strip RIFF/WAV header and return raw PCM payload."""
    import io
    import wave

    try:
        with io.BytesIO(wav_bytes) as bio:
            with wave.open(bio, "rb") as wav:
                return wav.readframes(wav.getnframes())
    except Exception as exc:
        _log.warning("Failed to strip WAV header, returning original bytes: %s", exc)
        return wav_bytes


class MiMoTTSProvider(TTSProvider):
    """Xiaomi MiMo text-to-speech provider."""

    def __init__(self) -> None:
        self._api_key = os.environ.get("MIMO_API_KEY", "").strip()
        self._model = os.environ.get("MIMO_TTS_MODEL", _DEFAULT_MODEL).strip()
        self._voice = os.environ.get("MIMO_TTS_VOICE", _DEFAULT_VOICE).strip()
        self._format = os.environ.get("MIMO_TTS_FORMAT", _DEFAULT_FORMAT).strip()

        if not self._api_key:
            raise ConfigurationError("MiMoTTSProvider requires MIMO_API_KEY.")

        _log.info(
            "MiMoTTSProvider initialized model=%s voice=%s format=%s",
            self._model,
            self._voice,
            self._format,
        )

    @property
    def default_voice(self) -> str:
        return self._voice

    def _build_mimo_request(self, text: str, voice: str) -> dict[str, Any]:
        """Build the request JSON dict for the MiMo chat completions endpoint."""
        return {
            "model": self._model,
            "messages": [
                {"role": "user", "content": ""},
                {"role": "assistant", "content": text},
            ],
            "audio": {
                "format": self._format,
                "voice": voice or self._voice,
            },
        }

    def _extract_mimo_audio(self, data: dict) -> str:
        """Extract the base64-encoded audio data from the MiMo response."""
        audio_b64 = data.get("choices", [{}])[0].get("message", {}).get("audio", {}).get("data")
        if not audio_b64:
            raise VoiceProviderError(f"MiMo TTS response did not contain audio data: {data}")
        return audio_b64

    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        """Synthesize text to PCM bytes via MiMo chat completions endpoint."""
        if not text or not text.strip():
            return b""

        request_json = self._build_mimo_request(text, voice)

        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(_CHAT_URL, json=request_json, headers=headers)
        except httpx.NetworkError as exc:
            raise NetworkError(f"MiMo TTS network error: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise NetworkError(f"MiMo TTS timeout: {exc}") from exc
        except Exception as exc:
            raise VoiceProviderError(f"MiMo TTS request failed: {exc}") from exc

        if resp.status_code in (401, 403):
            raise AuthenticationError(f"MiMo TTS authentication failed: {resp.status_code} {resp.text[:500]}")
        if resp.status_code != 200:
            raise VoiceProviderError(f"MiMo TTS HTTP {resp.status_code}: {resp.text[:500]}")

        try:
            data = resp.json()
        except Exception as exc:
            raise VoiceProviderError(f"MiMo TTS returned invalid JSON: {exc}") from exc

        audio_b64 = self._extract_mimo_audio(data)
        audio_bytes = base64.b64decode(audio_b64)
        _log.debug("MiMoTTS synthesized %d bytes model=%s", len(audio_bytes), self._model)

        if self._format == "wav":
            return _decode_wav_to_pcm(audio_bytes, sample_rate)
        # pcm16 is returned as raw 24kHz PCM; resample if necessary.
        if sample_rate == 24000:
            return audio_bytes
        return _decode_wav_to_pcm(_pcm_to_wav(audio_bytes, 24000), sample_rate)

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        """Stream-synthesize text fragments.

        MiMo supports streaming, but this provider currently buffers all text
        and synthesizes in one request for simplicity.
        """
        parts: list[str] = []
        async for fragment in text_stream:
            parts.append(fragment)
        full_text = "".join(parts)
        if not full_text.strip():
            return
        audio = await self.synthesize(full_text, voice=voice, sample_rate=sample_rate)
        if audio:
            yield audio


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """Wrap raw PCM s16le mono bytes in a WAV header for ffmpeg input."""
    import io
    import wave

    with io.BytesIO() as bio:
        with wave.open(bio, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm_bytes)
        return bio.getvalue()
