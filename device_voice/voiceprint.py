"""Voiceprint recognition provider (3D-Speaker).

Ported from xiaozhi-server core/utils/voiceprint_cache.py and
core/providers/voiceprint/. Provides speaker identification from
audio embeddings using 3D-Speaker (ERes2Net) or an external API.

Architecture:
  - Local mode: loads 3D-Speaker model via modelscope (try-import)
  - API mode: delegates to external voiceprint API (config-based)
  - Embedding cache: per-device known embeddings loaded from DB

Configuration via environment variables:
  LIMA_VOICEPRINT_MODE=local|api|off   (default: local)
  LIMA_VOICEPRINT_API_URL=<url>        (required for api mode)
  LIMA_VOICEPRINT_API_KEY=<key>        (required for api mode)
  LIMA_VOICEPRINT_SIMILARITY_THRESHOLD=0.6  (cosine similarity threshold)

3D-Speaker model: iic/speech_eres2net_large_sv_zh-cn_3dspeaker_16k
Embedding dimension: 512
Sample rate: 16000 Hz
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

_log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────

VOICEPRINT_MODE = os.environ.get("LIMA_VOICEPRINT_MODE", "local").strip().lower()
VOICEPRINT_API_URL = os.environ.get("LIMA_VOICEPRINT_API_URL", "").strip()
VOICEPRINT_API_KEY = os.environ.get("LIMA_VOICEPRINT_API_KEY", "").strip()
SIMILARITY_THRESHOLD = float(os.environ.get("LIMA_VOICEPRINT_SIMILARITY_THRESHOLD", "0.6"))

# 3D-Speaker model info
_MODEL_ID = "speech_eres2net_large_sv_zh-cn_3dspeaker_16k"
_EMBEDDING_DIM = 512
_SAMPLE_RATE = 16000


# ── Data Classes ───────────────────────────────────────────────────────────


@dataclass
class SpeakerIdentity:
    """Result of voiceprint identification."""

    member_id: str = ""
    display_name: str = ""
    confidence: float = 0.0
    is_known: bool = False
    speaker_ref: str = ""


@dataclass(frozen=True)
class VoiceprintEntry:
    """Cached voiceprint entry for a registered speaker."""

    member_id: int
    display_name: str
    member_type: str
    speaker_ref: str
    embedding_hash: str
    embedding: Optional[list[float]] = None
    status: str = "active"
    expires_at: Optional[datetime] = None

    @property
    def reenroll_required(self) -> bool:
        return self.expires_at is not None and self.expires_at <= _now_utc()


@dataclass
class VoiceprintPolicy:
    """Result of voiceprint policy check."""

    allowed: bool = True
    reason: str = "voiceprint_off"
    member: Optional[VoiceprintEntry] = None


# ── Voiceprint Cache ───────────────────────────────────────────────────────


class VoiceprintCache:
    """Per-device cache of known voiceprint entries."""

    def __init__(self):
        self._by_device: dict[str, list[VoiceprintEntry]] = {}
        self._loaded_at: dict[str, float] = {}

    def update_device(self, device_id: str, entries: list[dict]) -> list[VoiceprintEntry]:
        parsed = [_entry_from_payload(item) for item in entries]
        active = [entry for entry in parsed if entry.status == "active"]
        self._by_device[device_id] = active
        self._loaded_at[device_id] = time.monotonic()
        return list(active)

    def clear_device(self, device_id: str) -> int:
        removed = len(self._by_device.pop(device_id, []))
        self._loaded_at.pop(device_id, None)
        return removed

    def entries_for_device(self, device_id: str) -> list[VoiceprintEntry]:
        return list(self._by_device.get(device_id, []))

    def is_fresh(self, device_id: str, ttl_seconds: int) -> bool:
        loaded_at = self._loaded_at.get(device_id)
        if loaded_at is None:
            return False
        return time.monotonic() - loaded_at <= ttl_seconds


# ── Policy Decision ────────────────────────────────────────────────────────


def decide_voiceprint_policy(
    mode: str,
    entries: list[VoiceprintEntry],
    speaker_ref: Optional[str],
) -> VoiceprintPolicy:
    """Decide whether to allow a request based on voiceprint policy.

    Modes (ported from xiaozhi-server):
      - voiceprint_off: always allow, no identification
      - loose: allow even if unknown speaker
      - child: allow children + unknown, block adults
      - strict: block unknown speakers

    Args:
        mode: Policy mode string.
        entries: Active voiceprint entries for the device.
        speaker_ref: Matched speaker reference from 3D-Speaker.

    Returns:
        VoiceprintPolicy with allowed, reason, and matched member.
    """
    normalized_mode = (mode or "voiceprint_off").strip().lower()
    active_entries = [e for e in entries if e.status == "active"]

    if normalized_mode == "voiceprint_off":
        return VoiceprintPolicy(allowed=True, reason="voiceprint_off")

    # Try to match by speaker_ref
    matched = next(
        (e for e in active_entries if speaker_ref and e.speaker_ref == speaker_ref),
        None,
    )
    if matched is not None:
        reason = (
            "child_reenroll_required"
            if matched.member_type == "child" and matched.reenroll_required
            else "matched"
        )
        return VoiceprintPolicy(allowed=True, reason=reason, member=matched)

    if normalized_mode == "loose":
        return VoiceprintPolicy(allowed=True, reason="unknown_allowed")
    if normalized_mode == "child":
        child_entries = [e for e in active_entries if e.member_type == "child"]
        reason = "child_unknown_allowed" if child_entries else "child_no_profile_allowed"
        return VoiceprintPolicy(allowed=True, reason=reason)
    if normalized_mode == "strict":
        return VoiceprintPolicy(allowed=False, reason="unknown_rejected")
    return VoiceprintPolicy(allowed=False, reason="invalid_mode")


# ── 3D-Speaker Embedding Extractor ─────────────────────────────────────────


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
            import torch  # noqa: F401  — verify torch is available
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
            self._load_error = (
                "modelscope not installed; install with: pip install modelscope funasr"
            )
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


# ── Voiceprint Provider ────────────────────────────────────────────────────


class VoiceprintProvider:
    """Voiceprint recognition using speaker embeddings.

    The provider maintains a cache of known speaker embeddings
    (loaded from session_memory SQLite or manager-api).

    Supports two modes:
      - local: 3D-Speaker model loaded locally (requires torch + modelscope)
      - api: delegates to external voiceprint API
    """

    def __init__(self) -> None:
        self._model: Optional[_Model3DSpeaker] = None
        self._cache = VoiceprintCache()
        self._mode = VOICEPRINT_MODE
        self._enabled = self._mode != "off"

        if self._mode == "local":
            self._model = _Model3DSpeaker()
            _log.info("VoiceprintProvider mode=local (3D-Speaker, lazy-load)")
        elif self._mode == "api":
            if not VOICEPRINT_API_URL or not VOICEPRINT_API_KEY:
                _log.warning(
                    "VoiceprintProvider mode=api but URL/key not configured; disabled"
                )
                self._enabled = False
            else:
                _log.info("VoiceprintProvider mode=api url=%s", VOICEPRINT_API_URL)
        else:
            _log.info("VoiceprintProvider disabled (mode=%s)", self._mode)
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def cache(self) -> VoiceprintCache:
        return self._cache

    # ------------------------------------------------------------------
    # Embedding extraction
    # ------------------------------------------------------------------

    async def extract_embedding(self, wav_data: bytes) -> Optional[list[float]]:
        """Extract speaker embedding from WAV audio data.

        Args:
            wav_data: WAV-formatted 16kHz mono audio bytes.

        Returns:
            Embedding vector (list of floats) or None.
        """
        if not self._enabled:
            return None

        if self._mode == "local" and self._model is not None:
            if not self._model.available:
                self._model.load()
            if not self._model.available:
                _log.debug("3D-Speaker model not available; load_error=%s", self._model.load_error)
                return None
            import asyncio
            return await asyncio.to_thread(self._model.extract_embedding, wav_data)

        if self._mode == "api":
            return await self._extract_embedding_api(wav_data)

        return None

    # ------------------------------------------------------------------
    # Speaker identification
    # ------------------------------------------------------------------

    async def identify_speaker(
        self, wav_data: bytes, device_id: str
    ) -> SpeakerIdentity:
        """Identify the speaker from WAV audio data.

        Extracts embedding from wav_data, compares against cached
        embeddings for the device, and returns the best match.

        Args:
            wav_data: WAV-formatted audio bytes.
            device_id: Device identifier for loading device-specific embeddings.

        Returns:
            SpeakerIdentity with member_id, display_name, confidence, and is_known.
        """
        if not self._enabled:
            return SpeakerIdentity()

        # Extract embedding from input audio
        embedding = await self.extract_embedding(wav_data)
        if embedding is None:
            _log.debug("device=%s embedding extraction failed", device_id)
            return SpeakerIdentity()

        # Load known embeddings for this device
        entries = self._cache.entries_for_device(device_id)
        if not entries:
            await self._load_device_embeddings(device_id)
            entries = self._cache.entries_for_device(device_id)

        if not entries:
            _log.debug("device=%s no registered voiceprints", device_id)
            return SpeakerIdentity()

        # Compare against all known embeddings
        best_match: Optional[VoiceprintEntry] = None
        best_score = 0.0

        for entry in entries:
            if entry.embedding is None:
                continue
            score = _cosine_similarity(embedding, entry.embedding)
            if score > best_score:
                best_score = score
                best_match = entry

        if best_match is None or best_score < SIMILARITY_THRESHOLD:
            _log.info(
                "device=%s voiceprint unknown (best_score=%.3f threshold=%.3f)",
                device_id,
                best_score,
                SIMILARITY_THRESHOLD,
            )
            return SpeakerIdentity(
                confidence=best_score,
                is_known=False,
            )

        _log.info(
            "device=%s voiceprint matched: member=%s display=%s score=%.3f",
            device_id,
            best_match.member_id,
            best_match.display_name,
            best_score,
        )
        return SpeakerIdentity(
            member_id=str(best_match.member_id),
            display_name=best_match.display_name,
            confidence=best_score,
            is_known=True,
            speaker_ref=best_match.speaker_ref,
        )

    # ------------------------------------------------------------------
    # Speaker registration
    # ------------------------------------------------------------------

    async def register_speaker(
        self, wav_data: bytes, member_id: str, device_id: str
    ) -> Optional[list[float]]:
        """Extract and return speaker embedding from sample audio.

        The embedding can then be stored in the database by the caller.

        Args:
            wav_data: WAV-formatted sample audio.
            member_id: Family member identifier.
            device_id: Device that collected the sample.

        Returns:
            Embedding vector (list of floats) if extraction succeeded, else None.
        """
        if not self._enabled:
            _log.debug("Voiceprint registration skipped: provider disabled")
            return None

        embedding = await self.extract_embedding(wav_data)
        if embedding is None:
            _log.warning("device=%s member=%s embedding extraction failed", device_id, member_id)
            return None

        _log.info(
            "device=%s member=%s embedding extracted dim=%d",
            device_id,
            member_id,
            len(embedding),
        )
        return embedding

    # ------------------------------------------------------------------
    # Embedding cache management
    # ------------------------------------------------------------------

    async def _load_device_embeddings(self, device_id: str) -> None:
        """Load known voiceprint embeddings from the database for a device."""
        try:
            from session_memory.store_db import get_voiceprint_embeddings
            entries = get_voiceprint_embeddings(device_id)
            if entries:
                self._cache.update_device(device_id, entries)
                _log.info("device=%s loaded %d voiceprint entries", device_id, len(entries))
        except ImportError:
            _log.debug("session_memory.store_db not available")
        except Exception:
            _log.warning("device=%s failed to load voiceprint embeddings", device_id, exc_info=True)

    async def invalidate_cache(self, device_id: str) -> None:
        """Clear the voiceprint cache for a device."""
        self._cache.clear_device(device_id)
        _log.info("device=%s voiceprint cache cleared", device_id)

    # ------------------------------------------------------------------
    # API mode fallback
    # ------------------------------------------------------------------

    async def _extract_embedding_api(self, wav_data: bytes) -> Optional[list[float]]:
        """Extract embedding via external voiceprint API."""
        try:
            import aiohttp
        except ImportError:
            _log.warning("aiohttp not installed; cannot use API voiceprint mode")
            return None

        try:
            data = aiohttp.FormData()
            data.add_field("file", wav_data, filename="audio.wav", content_type="audio/wav")

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{VOICEPRINT_API_URL}/extract",
                    headers={"Authorization": f"Bearer {VOICEPRINT_API_KEY}"},
                    data=data,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        emb = result.get("embedding")
                        if isinstance(emb, list):
                            return emb
                    _log.warning("API embedding extraction failed: HTTP %d", response.status)
                    return None
        except Exception:
            _log.warning("API embedding extraction error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release model resources."""
        if self._model is not None:
            self._model.unload()
        self._cache.clear_device.__func__  # no-op reference
        _log.info("VoiceprintProvider closed")


# ── Singleton ──────────────────────────────────────────────────────────────

_voiceprint_instance: Optional[VoiceprintProvider] = None


def get_voiceprint_provider() -> VoiceprintProvider:
    """Return the singleton VoiceprintProvider instance."""
    global _voiceprint_instance
    if _voiceprint_instance is None:
        _voiceprint_instance = VoiceprintProvider()
    return _voiceprint_instance


# ── Helpers ────────────────────────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _entry_from_payload(payload: dict) -> VoiceprintEntry:
    """Parse a VoiceprintEntry from a manager-api JSON payload."""
    return VoiceprintEntry(
        member_id=int(payload.get("memberId") or payload.get("member_id") or 0),
        display_name=str(payload.get("displayName") or payload.get("display_name") or "").strip(),
        member_type=str(payload.get("memberType") or payload.get("member_type") or "").strip().lower(),
        speaker_ref=str(payload.get("speakerRef") or payload.get("speaker_ref") or "").strip(),
        embedding_hash=str(payload.get("embeddingHash") or payload.get("embedding_hash") or ""),
        embedding=payload.get("embedding"),
        status=str(payload.get("status") or "active").strip().lower(),
        expires_at=_parse_datetime(payload.get("expiresAt") or payload.get("expires_at")),
    )


def _parse_datetime(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)
