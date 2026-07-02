"""Volcano Engine (Doubao) ASR provider.

Implements the Doubao non-streaming ASR WebSocket protocol using the
`websockets` client library. This is a port of the reference implementation
from xiaozhi-server, adapted to LiMa's async ASRProvider interface.

Required env:
    DOUBAO_ASR_APPID
    DOUBAO_ASR_ACCESS_TOKEN
Optional env:
    DOUBAO_ASR_CLUSTER (default: volcengine_input_common)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import cast

import websockets

from config.settings import VOICE_PROVIDERS
from device_voice.asr import ASRProvider
from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)
from device_voice.providers.doubao_protocol import build_audio_frame, build_request_frame, parse_response

_log = logging.getLogger(__name__)

_DEFAULT_CLUSTER = "volcengine_input_common"
_WS_URL = "wss://openspeech.bytedance.com/api/v2/asr"
_SUCCESS_CODE = 1000
_NO_VOICE_CODE = 1013


class DoubaoASRProvider(ASRProvider):
    """Volcano Engine Doubao speech recognition."""

    def __init__(self) -> None:
        cfg = VOICE_PROVIDERS.doubao_asr
        self._appid = cfg.appid
        self._access_token = cfg.access_token
        self._cluster = cfg.cluster or _DEFAULT_CLUSTER

        if not self._appid or not self._access_token:
            raise ConfigurationError("DoubaoASRProvider requires DOUBAO_ASR_APPID and DOUBAO_ASR_ACCESS_TOKEN.")

        _log.info("DoubaoASRProvider initialized cluster=%s", self._cluster)

    def _build_request_payload(self, audio_data: bytes, sample_rate: int) -> dict:
        """Build the initial JSON payload for the Doubao ASR websocket."""
        return {
            "app": {
                "appid": self._appid,
                "cluster": self._cluster,
                "token": self._access_token,
            },
            "user": {"uid": str(uuid.uuid4())},
            "request": {
                "reqid": str(uuid.uuid4()),
                "show_utterances": False,
                "sequence": 1,
            },
            "audio": {
                "format": "raw",
                "rate": sample_rate,
                "language": "zh-CN",
                "bits": 16,
                "channel": 1,
                "codec": "raw",
            },
        }

    async def _send_initial_request(self, ws, audio_data: bytes, sample_rate: int) -> None:
        """Send the configuration frame and validate the server ack."""
        payload = self._build_request_payload(audio_data, sample_rate)
        await ws.send(build_request_frame(payload))
        response = cast(bytes, await ws.recv())
        result = parse_response(response)
        code = result.get("payload_msg", {}).get("code")
        if code not in (_SUCCESS_CODE, _NO_VOICE_CODE):
            raise _map_doubao_error(code, result.get("payload_msg", {}))

    async def _stream_audio_chunks(self, ws, audio_data: bytes) -> None:
        """Stream raw audio chunks to the ASR websocket."""
        chunk_size = 3200  # 100ms of 16-bit mono @ 16kHz
        total = len(audio_data)
        for offset in range(0, total, chunk_size):
            is_last = offset + chunk_size >= total
            chunk = audio_data[offset : offset + chunk_size]
            await ws.send(build_audio_frame(chunk, is_last=is_last))

    async def _read_final_transcript(self, ws) -> str:
        """Read the final ASR response and return the transcript text."""
        response = cast(bytes, await ws.recv())
        result = parse_response(response)
        payload = result.get("payload_msg", {})
        code = payload.get("code")
        if code == _NO_VOICE_CODE:
            return ""
        if code != _SUCCESS_CODE:
            raise _map_doubao_error(code, payload)

        results = payload.get("result", [])
        if results:
            return results[0].get("text", "").strip()
        return ""

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        """Recognize a complete utterance and return the transcript."""
        if not audio_data:
            return ""

        headers = {"Authorization": f"Bearer; {self._access_token}"}
        try:
            async with websockets.connect(_WS_URL, additional_headers=headers) as ws:
                await self._send_initial_request(ws, audio_data, sample_rate)
                await self._stream_audio_chunks(ws, audio_data)
                return await self._read_final_transcript(ws)
        except websockets.WebSocketException as exc:
            error_text = str(exc).lower()
            if "401" in error_text or "403" in error_text:
                raise AuthenticationError(f"Doubao ASR authentication failed: {exc}") from exc
            raise NetworkError(f"Doubao ASR websocket error: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, VoiceProviderError):
                raise
            error_text = str(exc).lower()
            if "401" in error_text or "403" in error_text:
                raise AuthenticationError(f"Doubao ASR authentication failed: {exc}") from exc
            raise VoiceProviderError(f"Doubao ASR request failed: {exc}") from exc

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        """Streaming ASR is not implemented for Doubao in this provider.

        The non-streaming protocol already covers LiMa's current dialogue
        pipeline, which buffers a complete utterance before calling ASR.
        """
        raise NotImplementedError(
            "DoubaoASRProvider.stream_transcribe is not implemented. Use transcribe() with a complete utterance."
        )
        yield  # pragma: no cover


def _map_doubao_error(code: int | None, payload: dict) -> VoiceProviderError:
    """Map a Doubao ASR error code to a typed exception."""
    message = payload.get("message", payload.get("error", "unknown error"))
    error_text = f"Doubao ASR error {code}: {message}"

    if code in (1001, 1002, 1003, 1004, 1005, 2001, 2002):
        return AuthenticationError(error_text)
    if code in (1006, 1007, 1008, 1009):
        return NetworkError(error_text)
    return VoiceProviderError(error_text)
