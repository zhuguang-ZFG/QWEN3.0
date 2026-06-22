"""DashScope (Aliyun/Bailian) TTS provider.

Uses the official DashScope SDK (`dashscope.audio.tts.SpeechSynthesizer`) to
synthesize speech with the existing `ALIYUN_API_KEY` (or explicit
`DASHSCOPE_API_KEY`). Returns raw PCM bytes (s16le, mono, target sample_rate).

Required env (either):
    DASHSCOPE_API_KEY
    ALIYUN_API_KEY
Optional env:
    DASHSCOPE_TTS_MODEL (default: sambert-zhichu-v1)
                        DashScope Sambert model names encode the voice.
"""

from __future__ import annotations

import io
import logging
import os
import wave
from collections.abc import AsyncIterator
from typing import Any

from device_voice.providers._env import _get_dashscope_api_key

from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)
from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)

_DEFAULT_MODEL = "sambert-zhichu-v1"


class DashScopeTTSProvider(TTSProvider):
    """DashScope text-to-speech using ALIYUN_API_KEY / DASHSCOPE_API_KEY."""

    def __init__(self) -> None:
        self._api_key = _get_dashscope_api_key()
        self._model = os.environ.get("DASHSCOPE_TTS_MODEL", _DEFAULT_MODEL).strip()

        if not self._api_key:
            raise ConfigurationError("DashScopeTTSProvider requires DASHSCOPE_API_KEY or ALIYUN_API_KEY.")

        try:
            import dashscope
        except ImportError as exc:
            raise ConfigurationError(
                "DashScopeTTSProvider requires 'dashscope' package. Install: pip install dashscope>=1.20"
            ) from exc

        self._dashscope = dashscope
        _log.info("DashScopeTTSProvider initialized model=%s", self._model)

    @property
    def default_voice(self) -> str:
        return self._model

    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        """Synthesize text to PCM bytes via DashScope SpeechSynthesizer."""
        if not text or not text.strip():
            return b""

        model = voice or self._model
        try:
            result = await self._run_synthesis(text, model=model, sample_rate=sample_rate)
        except VoiceProviderError:
            raise
        except Exception as exc:
            error_text = str(exc).lower()
            if "api key" in error_text or "authentication" in error_text or "auth" in error_text:
                raise AuthenticationError(f"DashScope TTS authentication failed: {exc}") from exc
            if "network" in error_text or "timeout" in error_text or "connection" in error_text:
                raise NetworkError(f"DashScope TTS network error: {exc}") from exc
            raise VoiceProviderError(f"DashScope TTS failed: {exc}") from exc

        response = result.get_response()
        if response is not None and response.status_code != 200:
            message = getattr(response, "message", "") or ""
            code = getattr(response, "code", "") or ""
            error_text = f"{code} {message}".lower()
            if "access denied" in error_text:
                raise AuthenticationError(f"DashScope TTS access denied ({code}): {message}")
            if "modelnotfound" in error_text or "model not found" in error_text:
                raise ConfigurationError(f"DashScope TTS model not found ({code}): {message}")
            raise VoiceProviderError(f"DashScope TTS request failed ({code}): {message}")

        audio = result.get_audio_data()
        if not audio:
            return b""

        # DashScope pcm format returns s16le mono raw PCM already.
        # wav format includes a WAV header; strip it to return raw PCM.
        if audio.startswith(b"RIFF"):
            return _strip_wav_header(audio)
        return audio

    async def _run_synthesis(self, text: str, *, model: str, sample_rate: int) -> Any:
        """Run the synchronous DashScope SDK call in a worker thread."""
        # Return type is dashscope.audio.tts.SpeechSynthesisResult; kept as Any
        # because dashscope is an optional runtime dependency.
        from functools import partial

        loop = __import__("asyncio").get_event_loop()
        call = partial(
            self._dashscope.audio.tts.SpeechSynthesizer.call,
            model,
            text,
            api_key=self._api_key,
            format="pcm",
            sample_rate=sample_rate,
        )
        return await loop.run_in_executor(None, call)

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        """Streaming TTS is not implemented for DashScope provider."""
        raise NotImplementedError("DashScopeTTSProvider.stream_synthesize is not implemented")


def _strip_wav_header(wav_bytes: bytes) -> bytes:
    """Strip RIFF/WAV header and return raw PCM payload."""
    try:
        with io.BytesIO(wav_bytes) as bio:
            with wave.open(bio, "rb") as wav:
                n_frames = wav.getnframes()
                return wav.readframes(n_frames)
    except Exception as exc:
        _log.warning("Failed to strip WAV header, returning original bytes: %s", exc)
        return wav_bytes
