"""FunASR local ASR provider — free, offline speech recognition.

Ported from xiaozhi-server core/providers/asr/fun_local.py.
Uses the FunASR SenseVoiceSmall model for Chinese speech recognition.

Dependency: pip install funasr modelscope
Model: SenseVoiceSmall (~200MB, auto-downloaded from ModelScope on first use)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from device_voice.asr import ASRProvider

_log = logging.getLogger(__name__)


class FunASRProvider(ASRProvider):
    """FunASR SenseVoiceSmall — local, offline ASR."""

    def __init__(self) -> None:
        self._model = None

    def _ensure_model(self) -> bool:
        """Lazy-load the FunASR model (heavy import)."""
        if self._model is not None:
            return True
        try:
            from funasr import AutoModel  # noqa: F401
        except ImportError:
            _log.warning("funasr not installed; ASR unavailable. Install: pip install funasr modelscope")
            return False

        try:
            self._model = AutoModel(
                model="iic/SenseVoiceSmall",
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                disable_update=True,
                hub="ms",
            )
            _log.info("FunASR SenseVoiceSmall model loaded")
            return True
        except Exception:
            _log.warning("FunASR model failed to load", exc_info=True)
            return False

    async def transcribe(self, audio_data: bytes, *, sample_rate: int = 16000) -> str:
        if not audio_data or not self._ensure_model():
            return ""

        try:
            import asyncio

            result = await asyncio.to_thread(
                self._model.generate,
                input=audio_data,
                cache={},
                language="auto",
                use_itn=True,
                batch_size_s=60,
            )
            if not result or not isinstance(result, list):
                return ""
            first = result[0]
            if isinstance(first, dict):
                return first.get("text", "").strip()
            return str(first).strip()
        except Exception:
            _log.warning("FunASR transcription failed", exc_info=True)
            return ""

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], *, sample_rate: int = 16000
    ) -> AsyncIterator[str]:
        chunks: list[bytes] = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        combined = b"".join(chunks)
        text = await self.transcribe(combined, sample_rate=sample_rate)
        if text:
            yield text

    async def close(self) -> None:
        self._model = None
