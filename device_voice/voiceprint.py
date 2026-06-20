"""Voiceprint recognition provider facade."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from device_voice.voiceprint_types import SpeakerIdentity, VoiceprintEntry, VoiceprintPolicy  # noqa: F401
from device_voice.voiceprint_cache import VoiceprintCache, _entry_from_payload  # noqa: F401
from device_voice.voiceprint_policy import decide_voiceprint_policy  # noqa: F401
from device_voice.providers.voiceprint_3dspeaker import _Model3DSpeaker
from device_voice.providers.voiceprint_api import extract_embedding_api  # noqa: F401

_log = logging.getLogger(__name__)

VOICEPRINT_MODE = os.environ.get("LIMA_VOICEPRINT_MODE", "local").strip().lower()
VOICEPRINT_API_URL = os.environ.get("LIMA_VOICEPRINT_API_URL", "").strip()
VOICEPRINT_API_KEY = os.environ.get("LIMA_VOICEPRINT_API_KEY", "").strip()
def _parse_similarity_threshold() -> float:
    raw = os.environ.get("LIMA_VOICEPRINT_SIMILARITY_THRESHOLD", "0.6")
    try:
        return float(raw)
    except (ValueError, TypeError):
        _log.warning("LIMA_VOICEPRINT_SIMILARITY_THRESHOLD=%r invalid; falling back to 0.6", raw)
        return 0.6


SIMILARITY_THRESHOLD = _parse_similarity_threshold()


class VoiceprintProvider:
    def __init__(self) -> None:
        self._model: Optional[_Model3DSpeaker] = None
        self.cache = VoiceprintCache()
        self._mode = VOICEPRINT_MODE
        self.enabled = self._mode != "off"
        if self._mode == "local":
            self._model = _Model3DSpeaker()
            _log.info("VoiceprintProvider mode=local (3D-Speaker, lazy-load)")
        elif self._mode == "api":
            if not VOICEPRINT_API_URL or not VOICEPRINT_API_KEY:
                _log.warning("VoiceprintProvider mode=api but URL/key not configured; disabled")
                self.enabled = False
            else:
                _log.info("VoiceprintProvider mode=api url=%s", VOICEPRINT_API_URL)
        else:
            _log.info("VoiceprintProvider disabled (mode=%s)", self._mode)
            self.enabled = False

    async def extract_embedding(self, wav_data: bytes) -> Optional[list[float]]:
        if not self.enabled:
            return None
        if self._mode == "local" and self._model is not None:
            if not self._model.available:
                self._model.load()
            if not self._model.available:
                _log.warning("3D-Speaker model not available; load_error=%s", self._model.load_error)
                return None
            return await asyncio.to_thread(self._model.extract_embedding, wav_data)
        if self._mode == "api":
            return await extract_embedding_api(wav_data, VOICEPRINT_API_URL, VOICEPRINT_API_KEY)
        return None

    async def identify_speaker(self, wav_data: bytes, device_id: str) -> SpeakerIdentity:
        from device_voice.voiceprint_policy import _identify_speaker_impl

        return await _identify_speaker_impl(
            self, wav_data, device_id, SIMILARITY_THRESHOLD, _cosine_similarity
        )

    async def register_speaker(self, wav_data: bytes, member_id: str, device_id: str) -> Optional[list[float]]:
        if not self.enabled:
            _log.warning("Voiceprint registration skipped: provider disabled (mode=%s)", self._mode)
            return None
        embedding = await self.extract_embedding(wav_data)
        if embedding is None:
            _log.warning("device=%s member=%s voiceprint embedding extraction failed", device_id, member_id)
            return None
        _log.info("device=%s member=%s voiceprint embedding extracted dim=%d", device_id, member_id, len(embedding))
        return embedding

    async def _load_device_embeddings(self, device_id: str) -> None:
        try:
            from session_memory.store_voiceprint import get_voiceprint_embeddings

            entries = get_voiceprint_embeddings(device_id)
            if entries:
                self.cache.update_device(device_id, entries)
                _log.info("device=%s loaded %d voiceprint entries", device_id, len(entries))
        except ImportError:
            _log.warning(
                "session_memory.store_voiceprint not available; device=%s voiceprints will not persist", device_id
            )
        except Exception:
            _log.warning("device=%s failed to load voiceprint embeddings", device_id, exc_info=True)

    async def invalidate_cache(self, device_id: str) -> None:
        self.cache.clear_device(device_id)
        _log.info("device=%s voiceprint cache cleared", device_id)

    async def close(self) -> None:
        if self._model is not None:
            self._model.unload()
        cleared_count = 0
        for device_id in list(self.cache._by_device.keys()):
            cleared_count += self.cache.clear_device(device_id)
        _log.info("VoiceprintProvider closed; cleared %d device caches", cleared_count)


_voiceprint_instance: Optional[VoiceprintProvider] = None


def get_voiceprint_provider() -> VoiceprintProvider:
    global _voiceprint_instance
    if _voiceprint_instance is None:
        _voiceprint_instance = VoiceprintProvider()
    return _voiceprint_instance


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
