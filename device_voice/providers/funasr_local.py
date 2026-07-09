"""Optional local FunASR provider (xiaozhi fun_local pattern, lazy import)."""

from __future__ import annotations

import asyncio
import logging
import re

from device_voice.audio_format import prepare_pcm
from device_voice.providers.base import AsrNotConfiguredError

_log = logging.getLogger(__name__)
_FUNASR_TAG = re.compile(r"<\|[^|]+\|>")


def strip_funasr_tags(text: str) -> str:
    """Remove FunASR markup tags such as <|zh|><|Speech|>."""
    return _FUNASR_TAG.sub("", text or "").strip()


class FunAsrLocalProvider:
    """Local ASR via FunASR AutoModel; requires optional ``funasr`` package."""

    def __init__(self, *, model_dir: str, language: str = "auto") -> None:
        self._model_dir = (model_dir or "").strip()
        self._language = (language or "auto").strip() or "auto"
        self._model = None

    async def transcribe(self, audio_data: bytes) -> str:
        if not audio_data:
            return ""
        pcm_data, _sample_rate = prepare_pcm(audio_data)
        return await asyncio.to_thread(self._transcribe_sync, pcm_data)

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self._model_dir:
            raise AsrNotConfiguredError("LIMA_VOICE_MODEL_DIR is not configured for FunASR")
        _warn_if_low_memory()
        try:
            from funasr import AutoModel
        except ImportError as exc:
            raise AsrNotConfiguredError("funasr package is not installed; pip install funasr for local ASR") from exc
        _log.info("loading FunASR model from %s", self._model_dir)
        self._model = AutoModel(model=self._model_dir, disable_update=True)
        return self._model

    def _transcribe_sync(self, pcm_data: bytes) -> str:
        model = self._load_model()
        result = model.generate(
            input=pcm_data,
            cache={},
            language=self._language,
            use_itn=True,
            batch_size_s=60,
        )
        if not result:
            raise RuntimeError("FunASR returned empty transcript")
        raw = str(result[0].get("text") or "")
        text = strip_funasr_tags(raw)
        if not text:
            raise RuntimeError("FunASR returned empty transcript")
        return text


def _warn_if_low_memory(*, minimum_gb: float = 2.0) -> None:
    """xiaozhi fun_local: refuse load when free RAM is below ~2 GB."""
    try:
        import psutil
    except ImportError:
        return
    available_gb = psutil.virtual_memory().available / (1024**3)
    if available_gb < minimum_gb:
        raise AsrNotConfiguredError(
            f"FunASR needs about {minimum_gb:.0f}GB free RAM; only {available_gb:.1f}GB available"
        )
