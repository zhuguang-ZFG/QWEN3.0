"""Shared helpers for device-app audio clip persistence."""

from __future__ import annotations

import sqlite3

from device_logic.audio_store import ext_for_content_type, write_audio_file
from device_logic.chat_store import persist_user_audio_clip
from device_logic.http import new_id


class AudioIdConflictError(ValueError):
    """Raised when an audio ID already belongs to another device."""


def save_device_audio_clip(
    conn: sqlite3.Connection,
    device_id: str,
    content: str,
    audio_data: bytes,
    *,
    content_type: str = "audio/wav",
    audio_id: str | None = None,
    duration_ms: int | None = None,
) -> dict[str, str] | None:
    """Write audio bytes to disk and link transcript in chat history."""
    clip_id = (audio_id or "").strip() or new_id()
    owners = conn.execute("SELECT DISTINCT device_id FROM v2_audio_record WHERE audio_id=?", (clip_id,)).fetchall()
    if any(row["device_id"] != device_id for row in owners):
        raise AudioIdConflictError("audioId already belongs to another device")
    storage_path = write_audio_file(
        device_id,
        clip_id,
        audio_data,
        ext=ext_for_content_type(content_type),
    )
    return persist_user_audio_clip(
        conn,
        device_id,
        content,
        clip_id,
        storage_path=storage_path,
        content_type=content_type,
        duration_ms=duration_ms,
    )
