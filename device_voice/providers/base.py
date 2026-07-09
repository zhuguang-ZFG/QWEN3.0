"""ASR provider protocol for device-app voice transcribe."""

from __future__ import annotations

from typing import Protocol


class AsrNotConfiguredError(RuntimeError):
    """Raised when no ASR backend is configured for production use."""


class AsrProvider(Protocol):
    async def transcribe(self, audio_data: bytes) -> str: ...
