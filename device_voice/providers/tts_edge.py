"""EdgeTTS provider — free Microsoft Edge text-to-speech.

Ported from xiaozhi-server core/providers/tts/edge.py.
Uses the edge-tts pip package (no API key required).

Dependency: pip install edge-tts
"""

from __future__ import annotations

import io
import logging
from collections.abc import AsyncIterator

from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)

# Default Chinese female voice
_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS — free, high-quality neural voices."""

    def __init__(self) -> None:
        self._voice = _DEFAULT_VOICE

    @property
    def default_voice(self) -> str:
        return self._voice

    async def synthesize(
        self, text: str, *, voice: str = "", sample_rate: int = 16000
    ) -> bytes:
        """Synthesize text to PCM audio via EdgeTTS.

        EdgeTTS produces MP3 audio; we return it directly (device can decode).
        For raw PCM output, pipe through ffmpeg (not done here to avoid dep).
        """
        if not text or not text.strip():
            return b""
        try:
            import edge_tts
        except ImportError:
            _log.warning("edge-tts not installed; TTS unavailable. Install: pip install edge-tts")
            return b""

        v = voice or self._voice
        communicate = edge_tts.Communicate(text, voice=v)
        audio_bytes = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])
        result = audio_bytes.getvalue()
        _log.debug("EdgeTTS synthesized %d bytes for voice=%s", len(result), v)
        return result

    async def stream_synthesize(
        self, text_stream: AsyncIterator[str], *, voice: str = "", sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        """Stream-synthesize text fragments into audio chunks."""
        v = voice or self._voice
        # Buffer all text then synthesize in one call (EdgeTTS doesn't support
        # true streaming input; this is acceptable for short replies).
        parts: list[str] = []
        async for fragment in text_stream:
            parts.append(fragment)
        full_text = "".join(parts)
        if full_text.strip():
            audio = await self.synthesize(full_text, voice=v, sample_rate=sample_rate)
            if audio:
                yield audio
