"""VAD (Voice Activity Detection) provider abstraction.

Ported from xiaozhi-server core/providers/vad/silero.py, simplified for
LiMa's per-session, stateless audio processing.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class VADState:
    """Per-connection VAD state. The device gateway creates one per WebSocket."""

    is_speaking: bool = False
    speech_buffer: bytearray = field(default_factory=bytearray)
    silence_frames: int = 0
    total_frames: int = 0


class VADProvider(ABC):
    """Abstract base for voice-activity-detection providers."""

    @abstractmethod
    def detect(self, audio_chunk: bytes, state: VADState) -> bool:
        """Process one audio chunk and update *state* in-place.

        Args:
            audio_chunk: Raw PCM bytes (16-bit mono, 16 kHz).
            state: Mutable per-connection VAD state.

        Returns:
            True if the chunk contains speech activity.
        """
        ...

    @abstractmethod
    def is_utterance_end(self, state: VADState) -> bool:
        """Return True when the current utterance has ended (silence threshold)."""
        ...

    def reset(self, state: VADState) -> None:
        """Reset state for a new utterance. Override for provider-specific cleanup."""
        state.is_speaking = False
        state.speech_buffer.clear()
        state.silence_frames = 0

    async def close(self) -> None:
        """Release model resources. Override if needed."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, str] = {
    "silero": "device_voice.providers.vad_silero.SileroVADProvider",
}


def create_vad_provider(name: str) -> VADProvider:
    """Instantiate the named VAD provider (lazy import)."""
    dotted = _PROVIDERS.get(name)
    if dotted is None:
        _log.warning("Unknown VAD provider '%s', falling back to 'silero'", name)
        dotted = _PROVIDERS["silero"]
    module_path, cls_name = dotted.rsplit(".", 1)
    import importlib

    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    return cls()
