"""TTS (Text-to-Speech) provider abstraction.

Ported from xiaozhi-server core/providers/tts/base.py, simplified for
LiMa's async-first design.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

_log = logging.getLogger(__name__)


class TTSProvider(ABC):
    """Abstract base for text-to-speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        """Synthesize text into raw PCM audio bytes (16-bit mono).

        Args:
            text: Text to synthesize.
            voice: Voice name / ID. Empty = provider default.
            sample_rate: Target sample rate in Hz.

        Returns:
            Raw PCM bytes. Empty bytes on failure.
        """
        ...

    @abstractmethod
    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        """Streaming TTS — yields audio chunks as text arrives.

        Args:
            text_stream: Async iterator of text fragments.
            voice: Voice name / ID.
            sample_rate: Target sample rate.

        Yields:
            PCM audio byte chunks.
        """
        ...

    async def close(self) -> None:
        """Release provider resources. Override if needed."""

    @property
    def default_voice(self) -> str:
        """Return the default voice for this provider."""
        return ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, str] = {
    "edge": "device_voice.providers.tts_edge.EdgeTTSProvider",
    "doubao": "device_voice.providers.tts_doubao.DoubaoTTSProvider",
    "aliyun": "device_voice.providers.tts_aliyun.AliyunTTSProvider",
    "dashscope": "device_voice.providers.tts_dashscope.DashScopeTTSProvider",
}


def create_tts_provider(name: str) -> TTSProvider:
    """Instantiate the named TTS provider (lazy import)."""
    dotted = _PROVIDERS.get(name)
    if dotted is None:
        _log.warning("Unknown TTS provider '%s', falling back to 'edge'", name)
        dotted = _PROVIDERS["edge"]
    module_path, cls_name = dotted.rsplit(".", 1)
    import importlib

    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    return cls()
