"""ASR (Automatic Speech Recognition) provider abstraction.

Ported from xiaozhi-server core/providers/asr/base.py, simplified for
LiMa's async-only, connection-state-free design.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

_log = logging.getLogger(__name__)


class ASRProvider(ABC):
    """Abstract base for speech-to-text providers."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        """Convert raw PCM audio (16-bit mono) to text.

        Args:
            audio_data: Raw PCM bytes, 16-bit signed little-endian mono.
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            Recognised text string. Empty string on failure.
        """
        ...

    @abstractmethod
    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        """Streaming ASR — yields partial/final transcripts as audio arrives.

        Args:
            audio_stream: Async iterator of PCM audio chunks.
            sample_rate: Sample rate in Hz.

        Yields:
            Intermediate transcript strings. The last yielded string is the
            final transcript for the utterance.
        """
        ...

    async def close(self) -> None:
        """Release provider resources (model, connections). Override if needed."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, str] = {
    "funasr": "device_voice.providers.asr_funasr.FunASRProvider",
    "aliyun": "device_voice.providers.asr_aliyun.AliyunASRProvider",
    "doubao": "device_voice.providers.asr_doubao.DoubaoASRProvider",
}


def create_asr_provider(name: str) -> ASRProvider:
    """Instantiate the named ASR provider (lazy import)."""
    dotted = _PROVIDERS.get(name)
    if dotted is None:
        _log.warning("Unknown ASR provider '%s', falling back to 'funasr'", name)
        dotted = _PROVIDERS["funasr"]
    module_path, cls_name = dotted.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    return cls()
