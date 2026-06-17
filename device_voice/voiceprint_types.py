"""Voiceprint data classes and datetime helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


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


__all__ = [
    "SpeakerIdentity",
    "VoiceprintEntry",
    "VoiceprintPolicy",
    "_parse_datetime",
    "_now_utc",
]
