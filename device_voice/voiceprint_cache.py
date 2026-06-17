"""Per-device voiceprint embedding cache."""

from __future__ import annotations

import logging
import time

from device_voice.voiceprint_types import VoiceprintEntry, _parse_datetime

_log = logging.getLogger(__name__)


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


__all__ = ["VoiceprintCache", "_entry_from_payload"]
