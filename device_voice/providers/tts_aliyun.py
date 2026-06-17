"""Alibaba Cloud TTS provider — high-quality cloud text-to-speech.

Ported from xiaozhi-server core/providers/tts/aliyun.py.

Required env: ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET
Note: This is a stub — full implementation requires Alibaba TTS SDK.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)


class AliyunTTSProvider(TTSProvider):
    """Alibaba Cloud TTS — high-quality neural voices."""

    def __init__(self) -> None:
        _log.warning(
            "AliyunTTSProvider is a stub — real Alibaba NLS TTS SDK integration is "
            "required before using this provider in production"
        )

    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        raise NotImplementedError(
            "Aliyun TTS is not implemented. Set LIMA_VOICE_TTS_PROVIDER=edge "
            "or implement device_voice.providers.tts_aliyun.AliyunTTSProvider."
        )

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError(
            "Aliyun TTS streaming is not implemented. Set LIMA_VOICE_TTS_PROVIDER=edge "
            "or implement device_voice.providers.tts_aliyun.AliyunTTSProvider.stream_synthesize."
        )
        yield  # pragma: no cover
