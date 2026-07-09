"""Streaming ASR session for device-app voice WebSocket."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable

from config.backend_config import ALIYUN_API_KEY
from config.voice_settings import VOICE, VOICE_PROVIDERS
from device_voice.asr import AsrNotConfiguredError, get_asr_provider, transcribe_audio
from device_voice.providers.dashscope import uses_streaming_model

_log = logging.getLogger(__name__)
TranscriptHandler = Callable[[str, bool], Awaitable[None]]


class BufferedVoiceStreamSession:
    """Collect PCM/WAV chunks and transcribe once on stop."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    async def feed(self, chunk: bytes) -> None:
        if chunk:
            self._chunks.append(chunk)

    async def finish(self) -> str:
        audio_data = b"".join(self._chunks)
        self._chunks.clear()
        if not audio_data:
            return ""
        return await transcribe_audio(audio_data)


class DashScopeLiveStreamSession:
    """Stream PCM frames through DashScope Recognition with partial transcripts."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handler: TranscriptHandler | None = None
        self._recognition = None
        self._collector = None
        self._error: Exception | None = None
        self._done: threading.Event | None = None
        self._started = False

    async def start(self, handler: TranscriptHandler) -> None:
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self._handler = handler
        await asyncio.to_thread(self._start_sync)

    async def feed(self, chunk: bytes) -> None:
        if not chunk or not self._started:
            return
        await asyncio.to_thread(self._feed_sync, chunk)

    async def finish(self) -> str:
        if not self._started:
            return ""
        return await asyncio.to_thread(self._finish_sync)

    def _start_sync(self) -> None:
        from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

        session = self

        class Collector(RecognitionCallback):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
                self.latest_partial = ""

            def on_event(self, result: RecognitionResult) -> None:
                sentence = result.get_sentence()
                if not isinstance(sentence, dict):
                    return
                text = str(sentence.get("text") or "").strip()
                if not text or session._loop is None or session._handler is None:
                    return
                is_final = RecognitionResult.is_sentence_end(sentence)
                if is_final:
                    self.parts.append(text)
                else:
                    self.latest_partial = text
                asyncio.run_coroutine_threadsafe(session._handler(text, is_final), session._loop)

            def on_error(self, result: RecognitionResult) -> None:
                session._error = RuntimeError(str(result))
                if session._done is not None:
                    session._done.set()

            def on_complete(self) -> None:
                if session._done is not None:
                    session._done.set()

        self._collector = Collector()
        self._error = None
        self._done = threading.Event()
        self._recognition = Recognition(
            model=self._model,
            format="pcm",
            sample_rate=16000,
            callback=self._collector,
            api_key=self._api_key,
            language_hints=["zh", "en"],
            semantic_punctuation_enabled=False,
        )
        self._recognition.start()
        self._started = True

    def _feed_sync(self, chunk: bytes) -> None:
        if self._recognition is not None:
            self._recognition.send_audio_frame(chunk)

    def _finish_sync(self) -> str:
        if self._recognition is None or self._collector is None or self._done is None:
            return ""
        try:
            self._recognition.stop()
        finally:
            self._done.wait(timeout=30.0)
            self._started = False
        if self._error is not None:
            raise self._error
        text = "".join(self._collector.parts).strip() or self._collector.latest_partial.strip()
        if not text:
            raise RuntimeError("ASR returned empty transcript")
        return text


async def open_voice_stream_session() -> BufferedVoiceStreamSession | DashScopeLiveStreamSession:
    """Return a streaming session matching the configured ASR provider."""
    if not VOICE.enabled:
        raise AsrNotConfiguredError("LIMA_VOICE_ENABLED is not set")
    provider_name = (VOICE.asr_provider or "dashscope").strip().lower()
    if provider_name == "dashscope":
        api_key = VOICE_PROVIDERS.dashscope_asr.api_key or ALIYUN_API_KEY
        model = (VOICE_PROVIDERS.dashscope_asr.model or "qwen3-asr-flash").strip()
        if api_key and uses_streaming_model(model):
            return DashScopeLiveStreamSession(api_key=api_key, model=model)
    get_asr_provider()
    return BufferedVoiceStreamSession()


def asr_available() -> bool:
    try:
        get_asr_provider()
    except AsrNotConfiguredError:
        return False
    return True
