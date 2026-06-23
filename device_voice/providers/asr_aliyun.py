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
import logging
import threading
from collections.abc import AsyncIterator
from typing import Any

from config.settings import VOICE_PROVIDERS

from device_voice.asr import ASRProvider
from device_voice.exceptions import AuthenticationError, ConfigurationError
from device_voice.providers._asr_aliyun_worker import (
    _map_nls_error,
    _parse_nls_result,
    _run_streaming_worker,
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
        result = _parse_nls_result(message)
        if result:
            with self.lock:
                self.final_text = result

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


def _get_token(ak_id: str, ak_secret: str, region: str) -> str:
    """Fetch an NLS token; the SDK may return a string or dict wrapper."""
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
        cfg = VOICE_PROVIDERS.aliyun_nls
        self._ak_id = cfg.ak_id
        self._ak_secret = cfg.ak_secret
        self._app_key = cfg.app_key
        self._region = cfg.region or _DEFAULT_REGION

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
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            None,
            _run_streaming_worker,
            queue,
            self._url,
            self._token,
            self._app_key,
            sample_rate,
        )

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
