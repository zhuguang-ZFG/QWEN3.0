"""Alibaba Cloud NLS ASR provider.

Uses the official Alibaba NLS Python SDK (`nls` package) for short-sentence
recognition and real-time transcription. Credentials are read from environment
variables at init time; missing credentials raise ConfigurationError.

Required env (aliases accepted):
    ALIBABA_CLOUD_ACCESS_KEY_ID  or  ALIYUN_AK_ID
    ALIBABA_CLOUD_ACCESS_KEY_SECRET  or  ALIYUN_AK_SECRET
    ALIBABA_NLS_APP_KEY
Optional env:
    ALIBABA_NLS_REGION (default: cn-shanghai)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections.abc import AsyncIterator
from typing import Any

from device_voice.asr import ASRProvider
from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)

_log = logging.getLogger(__name__)

_DEFAULT_REGION = "cn-shanghai"
_RECOGNIZER_URL_TEMPLATE = "wss://nls-gateway.{region}.aliyuncs.com/ws/v1"


class _RecognizerState:
    """Thread-safe result collector for NLS callback-style API."""

    def __init__(self) -> None:
        self.final_text = ""
        self.error_message: str | None = None
        self.completed = threading.Event()
        self.lock = threading.Lock()

    def on_result_changed(self, message: str, *_args: Any) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return
        result = payload.get("payload", {}).get("result", "")
        with self.lock:
            self.final_text = result

    def on_completed(self, message: str, *_args: Any) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            payload = {}
        result = payload.get("payload", {}).get("result", "")
        with self.lock:
            if result:
                self.final_text = result
        self.completed.set()

    def on_error(self, message: str, *_args: Any) -> None:
        self.error_message = message
        self.completed.set()

    def on_close(self, *_args: Any) -> None:
        self.completed.set()


def _get_env_with_aliases(*aliases: str) -> str:
    """Return the first non-empty environment variable value."""
    for name in aliases:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _get_token(ak_id: str, ak_secret: str, region: str) -> str:
    """Fetch an NLS access token from Alibaba Cloud.

    The official SDK may return either the token string directly or a dict
    wrapping ``{"Token": {"Id": "...", "ExpireTime": ...}}``.

    Raises:
        AuthenticationError: if the token request fails.
    """
    try:
        import nls.token

        token_response = nls.token.getToken(ak_id, ak_secret, domain=region)
    except Exception as exc:
        raise AuthenticationError(f"Failed to obtain Alibaba NLS token: {exc}") from exc

    if isinstance(token_response, str) and token_response:
        return token_response
    if isinstance(token_response, dict):
        token = token_response.get("Token", {}).get("Id")
        if token:
            return str(token)
    raise AuthenticationError(f"Invalid Alibaba NLS token response: {token_response}")


class AliyunASRProvider(ASRProvider):
    """Alibaba Cloud NLS speech recognition."""

    def __init__(self) -> None:
        self._ak_id = _get_env_with_aliases("ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIYUN_AK_ID")
        self._ak_secret = _get_env_with_aliases("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "ALIYUN_AK_SECRET")
        self._app_key = os.environ.get("ALIBABA_NLS_APP_KEY", "").strip()
        self._region = os.environ.get("ALIBABA_NLS_REGION", _DEFAULT_REGION).strip()

        if not self._ak_id or not self._ak_secret or not self._app_key:
            raise ConfigurationError(
                "AliyunASRProvider requires ALIBABA_CLOUD_ACCESS_KEY_ID, "
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET, and ALIBABA_NLS_APP_KEY."
            )

        self._token = _get_token(self._ak_id, self._ak_secret, self._region)
        self._url = _RECOGNIZER_URL_TEMPLATE.format(region=self._region)
        _log.info("AliyunASRProvider initialized for region=%s", self._region)

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        """Recognize a complete utterance and return the transcript."""
        if not audio_data:
            return ""

        def _sync_recognize() -> str:
            state = _RecognizerState()
            try:
                import nls
            except ImportError as exc:
                raise ConfigurationError("nls package not installed") from exc

            recognizer = nls.NlsSpeechRecognizer(
                url=self._url,
                token=self._token,
                appkey=self._app_key,
                on_result_changed=state.on_result_changed,
                on_completed=state.on_completed,
                on_error=state.on_error,
                on_close=state.on_close,
            )
            try:
                recognizer.start(
                    aformat="pcm",
                    sample_rate=sample_rate,
                    ch=1,
                    enable_intermediate_result=False,
                    enable_punctuation_prediction=True,
                    enable_inverse_text_normalization=True,
                    timeout=10,
                    ping_interval=8,
                    ping_timeout=None,
                )
                # Send audio in small chunks to avoid overwhelming the SDK.
                chunk_size = 3200  # 100ms of 16-bit mono @ 16kHz
                for offset in range(0, len(audio_data), chunk_size):
                    recognizer.send_audio(audio_data[offset : offset + chunk_size])
                recognizer.stop()
                state.completed.wait(timeout=30)
            finally:
                recognizer.shutdown()

            if state.error_message:
                raise _map_nls_error(state.error_message)
            return state.final_text.strip()

        return await asyncio.to_thread(_sync_recognize)

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        """Streaming ASR: yields partial/final transcripts.

        Note: NLS streaming transcription is callback-based; we bridge it to an
        async iterator by running the recognizer in a worker thread and feeding
        chunks from the async stream.
        """

        def _sync_stream(
            queue: asyncio.Queue[bytes | None],
            loop: asyncio.AbstractEventLoop,
        ) -> list[str]:
            state = _RecognizerState()
            results: list[str] = []

            def _on_result_changed(message: str, *_args: Any) -> None:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    return
                result = payload.get("payload", {}).get("result", "")
                if result:
                    results.append(result)

            state.on_result_changed = _on_result_changed

            try:
                import nls
            except ImportError as exc:
                raise ConfigurationError("nls package not installed") from exc

            transcriber = nls.NlsSpeechTranscriber(
                url=self._url,
                token=self._token,
                appkey=self._app_key,
                on_start=None,
                on_sentence_begin=None,
                on_sentence_end=state.on_completed,
                on_result_changed=state.on_result_changed,
                on_completed=state.on_completed,
                on_error=state.on_error,
                on_close=state.on_close,
            )

            try:
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

                while True:
                    try:
                        chunk = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        # Running in a worker thread; short blocking sleep is fine.
                        import time

                        time.sleep(0.01)
                        continue
                    if chunk is None:
                        break
                    transcriber.send_audio(chunk)

                transcriber.stop()
                state.completed.wait(timeout=30)
            finally:
                transcriber.shutdown()

            if state.error_message:
                raise _map_nls_error(state.error_message)
            return results

        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, _sync_stream, queue, loop)

        try:
            async for chunk in audio_stream:
                await queue.put(chunk)
            await queue.put(None)
            results = await future
            for text in results:
                yield text
        except Exception:
            await queue.put(None)
            if not future.done():
                future.cancel()
            raise


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
