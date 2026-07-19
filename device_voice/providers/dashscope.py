"""DashScope cloud ASR providers (one-shot + streaming)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import threading
import time

from device_voice.audio_format import ensure_wav_bytes, prepare_audio_for_streaming
from config.voice_settings import VOICE

_log = logging.getLogger(__name__)
_DEFAULT_ONESHOT_MODEL = "qwen3-asr-flash"
_DEFAULT_STREAM_MODEL = "paraformer-realtime-v2"
_LANGUAGE_HINTS = ["zh", "en"]


def uses_streaming_model(model: str) -> bool:
    normalized = model.lower()
    return "paraformer" in normalized or normalized.endswith("realtime-v2")


class Qwen3AsrFlashProvider:
    """One-shot ASR for hold-to-talk REST uploads."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model or _DEFAULT_ONESHOT_MODEL

    async def transcribe(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        return await asyncio.to_thread(self._transcribe_sync, audio_data)

    def _transcribe_sync(self, audio_data: bytes) -> str:
        from dashscope import MultiModalConversation

        wav_bytes = ensure_wav_bytes(audio_data)
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(wav_bytes)
                temp_path = temp_file.name

            response = MultiModalConversation.call(
                model=self._model,
                messages=[{"role": "user", "content": [{"audio": temp_path}]}],
                api_key=self._api_key,
                result_format="message",
                asr_options={"enable_lid": True, "enable_itn": True},
                stream=True,
            )
            text = extract_stream_text(response)
            if not text:
                raise RuntimeError("ASR returned empty transcript")
            return text
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError as exc:
                    _log.warning("failed to remove temp wav: %s", exc)


class DashScopeRecognitionProvider:
    """Streaming Recognition for paraformer-realtime-v2."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model or _DEFAULT_STREAM_MODEL

    async def transcribe(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        return await asyncio.to_thread(self._transcribe_sync, audio_data)

    def _build_recognition_collector(self):
        from dashscope.audio.asr import RecognitionCallback, RecognitionResult

        class Collector(RecognitionCallback):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
                self.latest_partial = ""
                self.error: RecognitionResult | None = None
                self._done = threading.Event()

            def on_event(self, result: RecognitionResult) -> None:
                sentence = result.get_sentence()
                if not isinstance(sentence, dict):
                    return
                text = str(sentence.get("text") or "").strip()
                if not text:
                    return
                if RecognitionResult.is_sentence_end(sentence):
                    self.parts.append(text)
                else:
                    self.latest_partial = text

            def on_error(self, result: RecognitionResult) -> None:
                self.error = result
                self._done.set()

            def on_complete(self) -> None:
                self._done.set()

            def wait(self, timeout: float = 30.0) -> None:
                self._done.wait(timeout=timeout)

        return Collector()

    def _stream_pcm_chunks(self, recognition, payload: bytes) -> None:
        chunk_size = max(160, VOICE.stream_pcm_frame_bytes)
        interval = max(0.0, VOICE.stream_frame_interval_ms / 1000.0)
        chunks = [payload[offset : offset + chunk_size] for offset in range(0, len(payload), chunk_size)]
        for index, chunk in enumerate(chunks):
            recognition.send_audio_frame(chunk)
            if index + 1 < len(chunks) and interval:
                time.sleep(interval)

    def _transcribe_sync(self, audio_data: bytes) -> str:
        from dashscope.audio.asr import Recognition

        payload, sample_rate, audio_format = prepare_audio_for_streaming(audio_data)
        collector = self._build_recognition_collector()
        recognition = Recognition(
            model=self._model,
            format=audio_format,
            sample_rate=sample_rate,
            callback=collector,
            api_key=self._api_key,
            language_hints=_LANGUAGE_HINTS,
            semantic_punctuation_enabled=False,
        )
        try:
            recognition.start()
        except Exception:
            # start() failed: do not call stop()/wait(); the SDK cleans its own
            # half-open connection, and on_complete/on_error will never fire,
            # so collector.wait() would block the full 30s for nothing.
            raise
        try:
            self._stream_pcm_chunks(recognition, payload)
        finally:
            try:
                recognition.stop()
            except Exception as exc:
                _log.warning("dashscope recognition stop failed: %s", type(exc).__name__)
            collector.wait()
        if collector.error is not None:
            raise RuntimeError(str(collector.error))
        text = "".join(collector.parts).strip() or collector.latest_partial.strip()
        if not text:
            raise RuntimeError("ASR returned empty transcript")
        return text


def extract_stream_text(response) -> str:
    latest = ""
    for chunk in response:
        try:
            content = chunk.output.choices[0].message.content[0]["text"]
        except (AttributeError, IndexError, KeyError, TypeError):
            try:
                content = chunk["output"]["choices"][0]["message"]["content"][0]["text"]
            except (KeyError, IndexError, TypeError):
                continue
        latest = str(content or "").strip()
    return latest
