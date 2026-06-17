"""Doubao (Volcano Engine) TTS provider — high-quality cloud text-to-speech.

Ported from xiaozhi-server core/providers/tts/doubao.py.

Required env: DOUBAO_TTS_APPID, DOUBAO_TTS_TOKEN
Note: This is a stub — full implementation requires Volcano Engine API.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)


class DoubaoTTSProvider(TTSProvider):
    """Volcano Engine TTS — high-quality neural voices."""

    def __init__(self) -> None:
        _log.info("DoubaoTTSProvider initialized (stub — API integration pending)")

    async def synthesize(
        self, text: str, *, voice: str = "", sample_rate: int = 16000
    ) -> bytes:
        _log.debug("Doubao TTS stub: returning empty (not yet implemented)")
        return b""

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        _log.debug("Doubao TTS stream stub: returning empty")
        return
        yield  # pragma: no cover
