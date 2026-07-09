"""Optional local Whisper ASR via faster-whisper (lazy import)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from config.voice_settings import VOICE_PROVIDERS
from device_voice.audio_format import ensure_wav_bytes
from device_voice.providers.base import AsrNotConfiguredError

_log = logging.getLogger(__name__)


class WhisperLocalProvider:
    """Local ASR via faster-whisper; requires optional ``faster-whisper`` package."""

    def __init__(
        self,
        *,
        model: str,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "",
    ) -> None:
        self._model_name = (model or "base").strip()
        self._device = (device or "cpu").strip() or "cpu"
        self._compute_type = (compute_type or "int8").strip() or "int8"
        self._language = (language or "").strip() or None
        self._model = None

    async def transcribe(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        return await asyncio.to_thread(self._transcribe_sync, audio_data)

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AsrNotConfiguredError(
                "faster-whisper package is not installed; pip install faster-whisper for Whisper ASR"
            ) from exc
        _log.info(
            "loading Whisper model=%s device=%s compute_type=%s",
            self._model_name,
            self._device,
            self._compute_type,
        )
        self._model = WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type,
        )
        return self._model

    def _transcribe_sync(self, audio_data: bytes) -> str:
        model = self._load_model()
        wav_bytes = ensure_wav_bytes(audio_data)
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(wav_bytes)
                temp_path = temp_file.name
            segments, _info = model.transcribe(temp_path, language=self._language)
            text = "".join(segment.text for segment in segments).strip()
            if not text:
                raise RuntimeError("Whisper returned empty transcript")
            return text
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError as exc:
                    _log.warning("failed to remove temp wav: %s", exc)


def whisper_config_or_default() -> tuple[str, str, str, str | None]:
    cfg = VOICE_PROVIDERS.whisper
    model = (cfg.model or "base").strip()
    device = (cfg.device or "cpu").strip() or "cpu"
    compute_type = (cfg.compute_type or "int8").strip() or "int8"
    language = (cfg.language or "").strip() or None
    return model, device, compute_type, language
