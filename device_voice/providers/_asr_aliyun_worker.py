"""Internal worker for Alibaba Cloud NLS streaming transcription."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)

_log = logging.getLogger(__name__)


def _parse_nls_result(message: str) -> str | None:
    """Extract the transcript result from an NLS JSON message."""
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return None
    result = payload.get("payload", {}).get("result", "")
    return result if result else None


class _StreamingRecognizerState:
    """Result collector that also keeps incremental transcripts."""

    def __init__(self) -> None:
        self.final_text = ""
        self.error_message: str | None = None
        self.completed = threading.Event()
        self.lock = threading.Lock()
        self.stream_results: list[str] = []

    def on_result_changed(self, message: str, *_args: Any) -> None:
        result = _parse_nls_result(message)
        if result:
            with self.lock:
                self.final_text = result
                self.stream_results.append(result)

    def on_completed(self, message: str, *_args: Any) -> None:
        result = _parse_nls_result(message)
        if result:
            with self.lock:
                self.final_text = result
        self.completed.set()

    def on_error(self, message: str, *_args: Any) -> None:
        self.error_message = message
        self.completed.set()

    def on_close(self, *_args: Any) -> None:
        self.completed.set()


def _create_streaming_transcriber(
    state: _StreamingRecognizerState, url: str, token: str, appkey: str
) -> Any:
    """Build an NlsSpeechTranscriber wired to *state* callbacks."""
    try:
        import nls
    except ImportError as exc:
        raise ConfigurationError("nls package not installed") from exc

    return nls.NlsSpeechTranscriber(
        url=url,
        token=token,
        appkey=appkey,
        on_start=None,
        on_sentence_begin=None,
        on_sentence_end=state.on_completed,
        on_result_changed=state.on_result_changed,
        on_completed=state.on_completed,
        on_error=state.on_error,
        on_close=state.on_close,
    )


def _start_streaming_transcriber(transcriber: Any, sample_rate: int) -> None:
    """Start the streaming transcriber with the standard PCM settings."""
    transcriber.start(
        aformat="pcm",
        sample_rate=sample_rate,
        ch=1,
        enable_intermediate_result=True,
        enable_punctuation_prediction=True,
        enable_inverse_text_normalization=True,
        timeout=10,
        ping_interval=8,
        ping_timeout=None,
    )


def _feed_audio_until_end(
    transcriber: Any, queue: asyncio.Queue[bytes | None]
) -> None:
    """Forward audio chunks from *queue* until a ``None`` sentinel arrives."""
    while True:
        try:
            chunk = queue.get_nowait()
        except asyncio.QueueEmpty:
            time.sleep(0.01)
            continue
        if chunk is None:
            break
        transcriber.send_audio(chunk)


def _stop_and_wait(transcriber: Any, state: _StreamingRecognizerState) -> None:
    """Signal end-of-stream and wait for the final callback."""
    transcriber.stop()
    state.completed.wait(timeout=30)


def _run_streaming_worker(
    queue: asyncio.Queue[bytes | None],
    url: str,
    token: str,
    appkey: str,
    sample_rate: int,
) -> list[str]:
    """Synchronous worker for NLS streaming transcription."""
    state = _StreamingRecognizerState()
    transcriber = _create_streaming_transcriber(state, url, token, appkey)
    try:
        _start_streaming_transcriber(transcriber, sample_rate)
        _feed_audio_until_end(transcriber, queue)
        _stop_and_wait(transcriber, state)
    finally:
        transcriber.shutdown()

    if state.error_message:
        raise _map_nls_error(state.error_message)
    return state.stream_results


def _map_nls_error(message: str) -> VoiceProviderError:
    """Map an NLS error JSON message to a typed exception."""
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return VoiceProviderError(message)

    status_code = payload.get("status_code")
    status_msg = payload.get("status_msg", "")
    error_text = f"Alibaba NLS error {status_code}: {status_msg}"

    if status_code in (40000001, 40000002, 40000003, 40100001, 40100002):
        return AuthenticationError(error_text)
    if status_code in (40020105, 40020106):
        return NetworkError(error_text)
    return VoiceProviderError(error_text)
