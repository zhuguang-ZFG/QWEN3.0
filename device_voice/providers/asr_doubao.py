"""Doubao (ByteDance/Volcano Engine) ASR provider — cloud speech recognition.

Ported from xiaozhi-server core/providers/asr/doubao.py.

Required env: DOUBAO_ASR_APPID, DOUBAO_ASR_TOKEN
Note: This is a stub — full implementation requires Volcano Engine SDK.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from device_voice.asr import ASRProvider

_log = logging.getLogger(__name__)


class DoubaoASRProvider(ASRProvider):
    """Volcano Engine ASR — high-quality cloud speech recognition."""

    def __init__(self) -> None:
        _log.info("DoubaoASRProvider initialized (stub — API integration pending)")

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        _log.debug("Doubao ASR stub: returning empty (not yet implemented)")
        return ""

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        _log.debug("Doubao ASR stream stub: returning empty")
        return
        yield  # pragma: no cover
