"""Composite Alibaba Cloud ASR provider with automatic fallback.

Runtime order:
    1. Alibaba Cloud NLS (`AliyunASRProvider`)
    2. DashScope realtime ASR (`DashScopeASRProvider`)
    3. Local faster-whisper (`WhisperASRProvider`)

The chain stops at the first provider that returns a transcript. Any provider
that fails to initialize or raises during transcription is logged and skipped.

Configuration is inherited from the individual providers; see their modules for
the required environment variables.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from device_voice.asr import ASRProvider
from device_voice.exceptions import ConfigurationError, VoiceProviderError
from device_voice.providers.asr_aliyun import AliyunASRProvider
from device_voice.providers.asr_dashscope import DashScopeASRProvider
from device_voice.providers.asr_whisper import WhisperASRProvider

_log = logging.getLogger(__name__)

# Names are resolved at runtime via globals() so tests can patch individual
# providers by replacing the module-level class references.
_PROVIDER_NAMES: list[tuple[str, str]] = [
    ("aliyun", "AliyunASRProvider"),
    ("dashscope", "DashScopeASRProvider"),
    ("whisper", "WhisperASRProvider"),
]


class AliyunFallbackASRProvider(ASRProvider):
    """Alibaba Cloud ASR with NLS → DashScope → Whisper fallback."""

    def __init__(self) -> None:
        self._providers: list[tuple[str, ASRProvider]] = []
        for name, cls_name in _PROVIDER_NAMES:
            try:
                cls = globals()[cls_name]
                provider = cls()
                self._providers.append((name, provider))
                _log.info("Fallback ASR provider initialized: %s", name)
            except VoiceProviderError as exc:
                _log.warning(
                    "Fallback ASR provider '%s' initialization skipped: %s",
                    name,
                    exc,
                )

        if not self._providers:
            raise ConfigurationError(
                "AliyunFallbackASRProvider: none of the fallback providers "
                "(aliyun, dashscope, whisper) could be initialized."
            )

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        """Transcribe audio, falling back through the provider chain."""
        if not audio_data:
            return ""

        last_error: VoiceProviderError | None = None
        for name, provider in self._providers:
            try:
                text = await provider.transcribe(audio_data, sample_rate=sample_rate)
                if text:
                    _log.info("Fallback ASR success via %s", name)
                    return text
                # Empty but successful result is valid (e.g. silence).
                return ""
            except VoiceProviderError as exc:
                _log.warning(
                    "Fallback ASR provider '%s' failed: %s",
                    name,
                    exc,
                )
                last_error = exc

        if last_error is not None:
            raise last_error
        raise VoiceProviderError("AliyunFallbackASRProvider: all providers failed")

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        """Streaming ASR by buffering audio and running the fallback chain.

        The composite provider does not yield intermediate partials because the
        fallback chain needs the complete utterance to decide which provider
        succeeds. The final transcript is yielded once.
        """
        chunks = [chunk async for chunk in audio_stream]
        combined = b"".join(chunks)
        text = await self.transcribe(combined, sample_rate=sample_rate)
        if text:
            yield text

    async def close(self) -> None:
        for _name, provider in self._providers:
            try:
                await provider.close()
            except Exception:
                _log.warning(
                    "Error closing fallback ASR provider '%s'",
                    _name,
                    exc_info=True,
                )
