"""DashScope (Aliyun/Bailian) ASR provider.

Uses the official DashScope SDK (`dashscope.audio.asr.Recognition`) for
real-time speech recognition. Adapts the streaming Recognition WebSocket to
the async ASRProvider interface. Credentials are read from `DASHSCOPE_API_KEY`
or the existing `ALIYUN_API_KEY`.

Required env (either):
    DASHSCOPE_API_KEY
    ALIYUN_API_KEY
Optional env:
    DASHSCOPE_ASR_MODEL (default: fun-asr-realtime)
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import AsyncIterator

from device_voice.providers._env import _get_dashscope_api_key

from device_voice.asr import ASRProvider
from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)

_log = logging.getLogger(__name__)

_DEFAULT_MODEL = "fun-asr-realtime"
_DEFAULT_FORMAT = "pcm"
_CHUNK_SIZE = 3200  # 100ms of 16-bit mono @ 16kHz


class _RecognitionCallback:
    """Callback that collects transcripts and signals completion."""

    def __init__(self) -> None:
        self.transcripts: list[str] = []
        self.error_message: str | None = None
        self.open_event = threading.Event()
        self.done_event = threading.Event()

    def on_open(self) -> None:
        self.open_event.set()

    def on_complete(self) -> None:
        self.done_event.set()

    def on_close(self) -> None:
        self.done_event.set()

    def on_error(self, result) -> None:  # noqa: ANN001
        try:
            self.error_message = str(result)
        except Exception:
            self.error_message = "unknown recognition error"
        self.done_event.set()

    def on_event(self, result) -> None:  # noqa: ANN001
        try:
            sentence = result.get_sentence()
        except Exception as exc:
            # Non-sentence events are expected in the streaming callback.
            _log.warning("DashScope ASR sentence extraction skipped: %s", exc)
            return
        if not sentence:
            return
        if isinstance(sentence, list):
            for s in sentence:
                text = s.get("text", "") if isinstance(s, dict) else ""
                if text:
                    self.transcripts.append(text)
        elif isinstance(sentence, dict):
            text = sentence.get("text", "")
            if text:
                self.transcripts.append(text)


class DashScopeASRProvider(ASRProvider):
    """DashScope speech recognition using ALIYUN_API_KEY / DASHSCOPE_API_KEY."""

    def __init__(self) -> None:
        self._api_key = _get_dashscope_api_key()
        self._model = os.environ.get("DASHSCOPE_ASR_MODEL", _DEFAULT_MODEL).strip()

        if not self._api_key:
            raise ConfigurationError("DashScopeASRProvider requires DASHSCOPE_API_KEY or ALIYUN_API_KEY.")

        try:
            import dashscope
        except ImportError as exc:
            raise ConfigurationError(
                "DashScopeASRProvider requires 'dashscope' package. Install: pip install dashscope>=1.20"
            ) from exc

        self._dashscope = dashscope
        _log.info("DashScopeASRProvider initialized model=%s", self._model)

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        """Recognize a complete utterance and return the transcript."""
        if not audio_data:
            return ""

        try:
            return await self._run_recognition(audio_data, sample_rate=sample_rate)
        except VoiceProviderError:
            raise
        except Exception as exc:
            error_text = str(exc).lower()
            if "api key" in error_text or "authentication" in error_text or "auth" in error_text:
                raise AuthenticationError(f"DashScope ASR authentication failed: {exc}") from exc
            if "network" in error_text or "timeout" in error_text or "connection" in error_text:
                raise NetworkError(f"DashScope ASR network error: {exc}") from exc
            raise VoiceProviderError(f"DashScope ASR failed: {exc}") from exc

    async def _run_recognition(self, audio_data: bytes, *, sample_rate: int) -> str:
        """Run synchronous DashScope Recognition in a worker thread."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._sync_recognize,
            audio_data,
            sample_rate,
        )

    def _sync_recognize(self, audio_data: bytes, sample_rate: int) -> str:
        """Synchronous wrapper around DashScope realtime recognition."""
        # Recognition reads the API key from dashscope.api_key global state;
        # set it for the duration of this call.
        previous_key = self._dashscope.api_key
        self._dashscope.api_key = self._api_key
        try:
            return self._do_sync_recognize(audio_data, sample_rate)
        finally:
            self._dashscope.api_key = previous_key

    def _do_sync_recognize(self, audio_data: bytes, sample_rate: int) -> str:
        """Core synchronous recognition logic."""
        callback = _RecognitionCallback()
        recognition = self._dashscope.audio.asr.Recognition(
            model=self._model,
            callback=callback,
            format=_DEFAULT_FORMAT,
            sample_rate=sample_rate,
        )

        try:
            recognition.start()
            if not callback.open_event.wait(timeout=10):
                raise NetworkError("DashScope ASR recognition did not open in time")

            # Stream audio in small chunks.
            total = len(audio_data)
            for offset in range(0, total, _CHUNK_SIZE):
                chunk = audio_data[offset : offset + _CHUNK_SIZE]
                recognition.send_audio_frame(chunk)
                # Tiny sleep to avoid overwhelming the WebSocket.
                time.sleep(0.005)

            recognition.stop()
            if not callback.done_event.wait(timeout=30):
                raise NetworkError("DashScope ASR recognition did not complete in time")
        except VoiceProviderError:
            raise
        except Exception as exc:
            raise NetworkError(f"DashScope ASR recognition error: {exc}") from exc

        if callback.error_message:
            raise VoiceProviderError(f"DashScope ASR error: {callback.error_message}")

        # Return the last complete transcript, or concatenated transcripts.
        if not callback.transcripts:
            return ""
        return callback.transcripts[-1].strip()

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        """Streaming ASR is not implemented for DashScope provider."""
        raise NotImplementedError("DashScopeASRProvider.stream_transcribe is not implemented")
