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
        _log.info("AliyunASRProvider initialized (stub — API integration pending)")

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        _log.debug("Aliyun ASR stub: returning empty (not yet implemented)")
        return ""

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        _log.debug("Aliyun ASR stream stub: returning empty")
        # Currently returns empty — full NLS SDK integration needed for streaming
        return
        yield  # pragma: no cover
