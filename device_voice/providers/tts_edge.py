"""EdgeTTS provider — free Microsoft Edge text-to-speech.

Ported from xiaozhi-server core/providers/tts/edge.py.
Uses the edge-tts pip package (no API key required).

Dependencies:
    pip install edge-tts
    ffmpeg binary available on PATH (for MP3 -> PCM conversion)
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
from collections.abc import AsyncIterator

from device_voice.tts import TTSProvider

_log = logging.getLogger(__name__)

# Default Chinese female voice
_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def _ffmpeg_available() -> bool:
    """Return True if the ffmpeg binary is available on PATH."""
    return shutil.which("ffmpeg") is not None


def _mp3_to_pcm(mp3_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Decode MP3 bytes to raw PCM (s16le, mono, target sample_rate).

    Raises:
        RuntimeError: if ffmpeg is not available or the conversion fails.
    """
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. EdgeTTS output is MP3 and must be "
            "converted to PCM before sending to the device. Install ffmpeg "
            "or set LIMA_VOICE_TTS_PROVIDER to a PCM-capable cloud provider."
        )

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "pipe:1",
        ],
        input=mp3_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"ffmpeg MP3->PCM conversion failed: {stderr}")
    return proc.stdout


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS — free, high-quality neural voices."""

    def __init__(self) -> None:
        self._voice = _DEFAULT_VOICE
        if not _ffmpeg_available():
            _log.warning(
                "ffmpeg not found on PATH. EdgeTTS output is MP3 and will fail "
                "at synthesis time unless the device firmware can decode MP3."
            )

    @property
    def default_voice(self) -> str:
        return self._voice

    async def synthesize(self, text: str, *, voice: str = "", sample_rate: int = 16000) -> bytes:
        """Synthesize text to PCM audio via EdgeTTS.

        EdgeTTS produces MP3 audio, which is decoded to PCM (s16le, mono,
        target sample_rate) using ffmpeg. If ffmpeg is unavailable, a clear
        RuntimeError is raised instead of silently returning MP3 bytes.
        """
        if not text or not text.strip():
            return b""
        try:
            import edge_tts
        except ImportError:
            _log.warning("edge-tts not installed; TTS unavailable. Install: pip install edge-tts")
            raise RuntimeError(
                "edge-tts is not installed. Install with: pip install edge-tts"
            ) from None

        v = voice or self._voice
        communicate = edge_tts.Communicate(text, voice=v)
        audio_bytes = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])
        mp3_data = audio_bytes.getvalue()
        _log.debug("EdgeTTS synthesized %d MP3 bytes for voice=%s", len(mp3_data), v)

        # EdgeTTS returns MP3; the device protocol expects PCM.
        return _mp3_to_pcm(mp3_data, sample_rate=sample_rate)

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
