"""Alibaba Cloud NLS TTS provider.

Uses the official Alibaba NLS Python SDK (`nls` package) for text-to-speech.
Returns raw PCM bytes (s16le, mono, target sample_rate). Credentials are read
from environment variables at init time; missing credentials raise
ConfigurationError.

Required env:
    ALIBABA_CLOUD_ACCESS_KEY_ID
    ALIBABA_CLOUD_ACCESS_KEY_SECRET
    ALIBABA_NLS_APP_KEY
Optional env:
    ALIBABA_NLS_REGION (default: cn-shanghai)
    ALIBABA_NLS_TTS_VOICE (default: xiaoyun)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections.abc import AsyncIterator
from typing import Any

from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)
from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)

_DEFAULT_REGION = "cn-shanghai"
_DEFAULT_VOICE = "xiaoyun"
_TTS_URL_TEMPLATE = "wss://nls-gateway.{region}.aliyuncs.com/ws/v1"


class _SynthesizerState:
    """Thread-safe audio collector for NLS TTS callbacks."""

    def __init__(self) -> None:
        self.audio_parts: list[bytes] = []
        self.error_message: str | None = None
        self.completed = threading.Event()
        self.lock = threading.Lock()

    def on_data(self, data: bytes, *_args: Any) -> None:
        if data:
            with self.lock:
                self.audio_parts.append(data)

    def on_completed(self, _message: str, *_args: Any) -> None:
        self.completed.set()

    def on_error(self, message: str, *_args: Any) -> None:
        self.error_message = message
        self.completed.set()

    def on_close(self, *_args: Any) -> None:
        self.completed.set()

    def get_audio(self) -> bytes:
        with self.lock:
            return b"".join(self.audio_parts)


def _get_token(ak_id: str, ak_secret: str, region: str) -> str:
    """Fetch an NLS access token from Alibaba Cloud."""
    try:
        import nls.token

        token_response = nls.token.getToken(ak_id, ak_secret, domain=region)
    except Exception as exc:
        raise AuthenticationError(f"Failed to obtain Alibaba NLS token: {exc}") from exc

    if isinstance(token_response, dict):
        token = token_response.get("Token", {}).get("Id")
        if token:
            return str(token)
    raise AuthenticationError(f"Invalid Alibaba NLS token response: {token_response}")


class AliyunTTSProvider(TTSProvider):
    """Alibaba Cloud NLS text-to-speech."""

    def __init__(self) -> None:
        self._ak_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", "").strip()
        self._ak_secret = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "").strip()
        self._app_key = os.environ.get("ALIBABA_NLS_APP_KEY", "").strip()
        self._region = os.environ.get("ALIBABA_NLS_REGION", _DEFAULT_REGION).strip()
        self._voice = os.environ.get("ALIBABA_NLS_TTS_VOICE", _DEFAULT_VOICE).strip()

        if not self._ak_id or not self._ak_secret or not self._app_key:
            raise ConfigurationError(
                "AliyunTTSProvider requires ALIBABA_CLOUD_ACCESS_KEY_ID, "
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET, and ALIBABA_NLS_APP_KEY."
            )

        self._token = _get_token(self._ak_id, self._ak_secret, self._region)
        self._url = _TTS_URL_TEMPLATE.format(region=self._region)
        _log.info("AliyunTTSProvider initialized for region=%s voice=%s", self._region, self._voice)

    @property
    def default_voice(self) -> str:
        return self._voice

    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        """Synthesize text into PCM audio bytes."""
        if not text or not text.strip():
            return b""

        v = voice or self._voice

        def _sync_synthesize() -> bytes:
            state = _SynthesizerState()
            try:
                import nls
            except ImportError as exc:
                raise ConfigurationError("nls package not installed") from exc

            synthesizer = nls.NlsSpeechSynthesizer(
                url=self._url,
                token=self._token,
                appkey=self._app_key,
                on_metainfo=None,
                on_data=state.on_data,
                on_completed=state.on_completed,
                on_error=state.on_error,
                on_close=state.on_close,
            )
            try:
                synthesizer.start(
                    text=text,
                    voice=v,
                    aformat="pcm",
                    sample_rate=sample_rate,
                    volume=50,
                    speech_rate=0,
                    pitch_rate=0,
                    wait_complete=True,
                    start_timeout=10,
                    completed_timeout=60,
                )
                state.completed.wait(timeout=70)
            finally:
                synthesizer.shutdown()

            if state.error_message:
                raise _map_nls_error(state.error_message)
            return state.get_audio()

        return await asyncio.to_thread(_sync_synthesize)

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        """Stream-synthesize text fragments.

        NLS TTS does not accept a true streaming text input, so we buffer all
        fragments and synthesize in one request.
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


def _map_nls_error(message: str) -> VoiceProviderError:
    """Map an NLS error JSON message to a typed exception."""
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return VoiceProviderError(message)

    status_code = payload.get("status_code")
    status_msg = payload.get("status_msg", "")
    error_text = f"Alibaba NLS TTS error {status_code}: {status_msg}"

    if status_code in (40000001, 40000002, 40000003, 40100001, 40100002):
        return AuthenticationError(error_text)
    if status_code in (40020105, 40020106):
        return NetworkError(error_text)
    return VoiceProviderError(error_text)
