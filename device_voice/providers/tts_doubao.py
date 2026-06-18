"""Volcano Engine (Doubao) TTS provider.

Uses the Doubao HTTP TTS API (`openspeech.bytedance.com/api/v1/tts`).
Credentials are read from environment variables at init time.

Required env:
    DOUBAO_TTS_APPID
    DOUBAO_TTS_ACCESS_TOKEN
Optional env:
    DOUBAO_TTS_CLUSTER (default: volcano_tts)
    DOUBAO_TTS_VOICE (default: zh_female_wanwanxiaohe_moon_bigtts)
    DOUBAO_TTS_ENCODING (default: pcm)
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from collections.abc import AsyncIterator

import httpx

from device_voice.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    VoiceProviderError,
)
from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)

_DEFAULT_CLUSTER = "volcano_tts"
_DEFAULT_VOICE = "zh_female_wanwanxiaohe_moon_bigtts"
_DEFAULT_ENCODING = "pcm"
_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"


class DoubaoTTSProvider(TTSProvider):
    """Volcano Engine Doubao text-to-speech."""

    def __init__(self) -> None:
        self._appid = os.environ.get("DOUBAO_TTS_APPID", "").strip()
        self._access_token = os.environ.get("DOUBAO_TTS_ACCESS_TOKEN", "").strip()
        self._cluster = os.environ.get("DOUBAO_TTS_CLUSTER", _DEFAULT_CLUSTER).strip()
        self._voice = os.environ.get("DOUBAO_TTS_VOICE", _DEFAULT_VOICE).strip()
        self._encoding = os.environ.get("DOUBAO_TTS_ENCODING", _DEFAULT_ENCODING).strip()

        if not self._appid or not self._access_token:
            raise ConfigurationError("DoubaoTTSProvider requires DOUBAO_TTS_APPID and DOUBAO_TTS_ACCESS_TOKEN.")

        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{self._access_token}",
        }
        _log.info(
            "DoubaoTTSProvider initialized cluster=%s voice=%s encoding=%s",
            self._cluster,
            self._voice,
            self._encoding,
        )

    @property
    def default_voice(self) -> str:
        return self._voice

    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        """Synthesize text into audio bytes (PCM by default)."""
        if not text or not text.strip():
            return b""

        v = voice or self._voice
        request_json = {
            "app": {
                "appid": self._appid,
                "token": self._access_token,
                "cluster": self._cluster,
            },
            "user": {"uid": "1"},
            "audio": {
                "voice_type": v,
                "encoding": self._encoding,
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(_TTS_URL, json=request_json, headers=self._headers)
        except httpx.NetworkError as exc:
            raise NetworkError(f"Doubao TTS network error: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Doubao TTS timeout: {exc}") from exc
        except Exception as exc:
            raise VoiceProviderError(f"Doubao TTS request failed: {exc}") from exc

        if resp.status_code != 200:
            raise _map_http_error(resp.status_code, resp.text)

        data = resp.json()
        if "data" not in data:
            raise VoiceProviderError(f"Doubao TTS unexpected response: {data}")

        audio_bytes = base64.b64decode(data["data"])
        _log.debug("DoubaoTTS synthesized %d bytes encoding=%s", len(audio_bytes), self._encoding)

        if self._encoding == "pcm":
            return audio_bytes

        # For non-PCM encodings (e.g. mp3, wav), return as-is. The caller/device
        # protocol may need additional decoding depending on the chosen format.
        return audio_bytes

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        """Stream-synthesize text fragments.

        Doubao HTTP TTS does not accept streaming text input, so we buffer all
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


def _map_http_error(status_code: int, body: str) -> VoiceProviderError:
    """Map an HTTP error to a typed exception."""
    error_text = f"Doubao TTS HTTP {status_code}: {body[:500]}"
    if status_code in (401, 403):
        return AuthenticationError(error_text)
    if status_code in (408, 502, 503, 504):
        return NetworkError(error_text)
    return VoiceProviderError(error_text)
