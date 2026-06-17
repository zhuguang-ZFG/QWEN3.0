"""3D-Speaker local embedding extractor."""

from __future__ import annotations

import logging
from typing import Optional

_log = logging.getLogger(__name__)

_MODEL_ID = "speech_eres2net_large_sv_zh-cn_3dspeaker_16k"
_EMBEDDING_DIM = 512
_SAMPLE_RATE = 16000


class _Model3DSpeaker:
    """Wrapper around 3D-Speaker ERes2Net model for embedding extraction.

    Uses modelscope pipeline for inference. Lazy-loaded on first use.
    Supports both local (GPU/CPU) and API-based extraction.
    """

    def __init__(self) -> None:
        self._pipeline = None
        self._loaded = False
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._loaded

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def load(self, device: str = "cpu") -> bool:
        """Try to load the 3D-Speaker model.

        Returns True if the model loaded successfully.
        """
        if self._loaded:
            return True

        try:
            import torch  # noqa: F401
        except ImportError:
            self._load_error = "torch not installed; install with: pip install torch"
            _log.warning("3D-Speaker not available: %s", self._load_error)
            return False

        try:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks

            self._pipeline = pipeline(
                Tasks.speaker_verification,
                model=f"iic/{_MODEL_ID}",
                device=device,
            )
            self._loaded = True
            _log.info("3D-Speaker model loaded: iic/%s (device=%s)", _MODEL_ID, device)
            return True
        except ImportError:
            self._load_error = "modelscope not installed; install with: pip install modelscope funasr"
            _log.warning("3D-Speaker not available: %s", self._load_error)
            return False
        except Exception as exc:
            self._load_error = f"model load failed: {exc}"
            _log.warning("3D-Speaker load failed: %s", exc)
            return False

    def extract_embedding(self, wav_data: bytes) -> Optional[list[float]]:
        """Extract speaker embedding from WAV audio bytes.

        Args:
            wav_data: WAV-formatted 16kHz mono audio bytes.

        Returns:
            512-dim embedding vector as list of floats, or None on failure.
        """
        if not self._loaded or self._pipeline is None:
            return None

        try:
            result = self._pipeline(wav_data)
            if isinstance(result, dict):
                embedding = result.get("output_embedding") or result.get("embedding")
                if embedding is not None:
                    if hasattr(embedding, "tolist"):
                        return embedding.tolist()
                    if isinstance(embedding, list):
                        return embedding
            _log.debug("Unexpected pipeline result format: %s", type(result).__name__)
            return None
        except Exception:
            _log.warning("Embedding extraction failed", exc_info=True)
            return None

    def unload(self) -> None:
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
        self._loaded = False
        self._load_error = None


__all__ = ["_Model3DSpeaker"]
