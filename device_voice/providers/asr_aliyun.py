"""Alibaba Cloud ASR provider — streaming-capable cloud speech recognition.

Ported from xiaozhi-server core/providers/asr/aliyun.py + aliyun_stream.py.

Required env: ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET
Note: This is a stub — full implementation requires the Alibaba NLS SDK.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from device_voice.asr import ASRProvider

_log = logging.getLogger(__name__)


class AliyunASRProvider(ASRProvider):
    """Alibaba Cloud ASR — streaming cloud speech recognition."""

    def __init__(self) -> None:
        _log.warning(
            "AliyunASRProvider is a stub — real Alibaba NLS SDK integration is "
            "required before using this provider in production"
        )

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        raise NotImplementedError(
            "Aliyun ASR is not implemented. Set LIMA_VOICE_ASR_PROVIDER=funasr "
            "or implement device_voice.providers.asr_aliyun.AliyunASRProvider."
        )

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        raise NotImplementedError(
            "Aliyun ASR streaming is not implemented. Set LIMA_VOICE_ASR_PROVIDER=funasr "
            "or implement device_voice.providers.asr_aliyun.AliyunASRProvider.stream_transcribe."
        )
        yield  # pragma: no cover
