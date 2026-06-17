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
        _log.warning(
            "DoubaoASRProvider is a stub — real Volcano Engine ASR SDK integration is "
            "required before using this provider in production"
        )

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        raise NotImplementedError(
            "Doubao ASR is not implemented. Set LIMA_VOICE_ASR_PROVIDER=funasr "
            "or implement device_voice.providers.asr_doubao.DoubaoASRProvider."
        )

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        raise NotImplementedError(
            "Doubao ASR streaming is not implemented. Set LIMA_VOICE_ASR_PROVIDER=funasr "
            "or implement device_voice.providers.asr_doubao.DoubaoASRProvider.stream_transcribe."
        )
        yield  # pragma: no cover
