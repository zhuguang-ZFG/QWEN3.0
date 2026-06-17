"""Local Whisper ASR provider using faster-whisper.

faster-whisper is a lightweight, CPU-friendly reimplementation of OpenAI
Whisper. It is a good fit for the LiMa VPS because the tiny/base models use
far less RAM than FunASR SenseVoiceSmall.

Optional env:
    WHISPER_MODEL         (default: tiny)   -- tiny/base/small/medium/large
    WHISPER_DEVICE        (default: cpu)
    WHISPER_COMPUTE_TYPE  (default: int8)   -- int8/float16/float32
    WHISPER_LANGUAGE      (default: empty = auto-detect)

Dependency:
    pip install faster-whisper
"""

from __future__ import annotations

import io
import logging
import os
import wave
from collections.abc import AsyncIterator
from typing import Any

from device_voice.asr import ASRProvider
from device_voice.exceptions import ConfigurationError, ModelUnavailableError, VoiceProviderError

try:
    from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover - handled at runtime
    WhisperModel = None  # type: ignore[misc,assignment]

_log = logging.getLogger(__name__)

_DEFAULT_MODEL = "tiny"
_DEFAULT_DEVICE = "cpu"
_DEFAULT_COMPUTE_TYPE = "int8"


class WhisperASRProvider(ASRProvider):
    """Local faster-whisper ASR.

    The model is loaded lazily on the first transcription call and cached for
    reuse. This keeps import-time dependencies light.
    """

    def __init__(self) -> None:
        self._model_name = os.environ.get("WHISPER_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
        self._device = os.environ.get("WHISPER_DEVICE", _DEFAULT_DEVICE).strip() or _DEFAULT_DEVICE
        self._compute_type = (
            os.environ.get("WHISPER_COMPUTE_TYPE", _DEFAULT_COMPUTE_TYPE).strip() or _DEFAULT_COMPUTE_TYPE
        )
        self._language = os.environ.get("WHISPER_LANGUAGE", "").strip() or None
        self._model: Any | None = None

        if WhisperModel is None:
            raise ConfigurationError(
                "WhisperASRProvider requires 'faster-whisper'. Install: pip install faster-whisper"
            )

        _log.info(
            "WhisperASRProvider initialized model=%s device=%s compute_type=%s",
            self._model_name,
            self._device,
            self._compute_type,
        )

    def _ensure_model(self) -> Any:
        """Lazy-load the faster-whisper model."""
        if self._model is not None:
            return self._model
        if WhisperModel is None:
            raise ConfigurationError("faster-whisper is not installed")

        try:
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
            _log.info("Whisper model loaded: %s", self._model_name)
        except Exception as exc:
            _log.warning("Whisper model failed to load", exc_info=True)
            raise ModelUnavailableError(f"Failed to load Whisper model {self._model_name}: {exc}") from exc
        return self._model

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM s16le mono audio to text."""
        if not audio_data:
            return ""

        model = self._ensure_model()
        wav_bytes = _pcm_to_wav(audio_data, sample_rate)

        try:
            import asyncio

            result = await asyncio.to_thread(
                self._transcribe_sync,
                model,
                wav_bytes,
            )
            return result
        except ModelUnavailableError:
            raise
        except Exception as exc:
            _log.warning("Whisper transcription failed", exc_info=True)
            raise VoiceProviderError(f"Whisper transcription failed: {exc}") from exc

    def _transcribe_sync(self, model: Any, wav_bytes: bytes) -> str:
        """Synchronous transcription helper."""
        segments, _info = model.transcribe(
            io.BytesIO(wav_bytes),
            language=self._language,
            beam_size=5,
        )
        return "".join(segment.text for segment in segments).strip()

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        """Streaming ASR buffers all audio and transcribes once."""
        chunks: list[bytes] = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        combined = b"".join(chunks)
        text = await self.transcribe(combined, sample_rate=sample_rate)
        if text:
            yield text

    async def close(self) -> None:
        self._model = None


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """Wrap raw PCM s16le mono bytes in a WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()
