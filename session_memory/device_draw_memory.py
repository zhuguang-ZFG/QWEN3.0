"""Persist device draw failure prompts in session_memory for retry hints."""

from __future__ import annotations

import logging

from session_memory.store import delete_memories_by_type, delete_memory, query_by_type, save_typed_memory

logger = logging.getLogger(__name__)

DEVICE_DRAW_FAILED = "device_draw_failed"
_MAX_FAILED = 5


def device_session_id(device_id: str) -> str:
    """Scope draw failures to a stable device session key."""
    return f"device:{device_id}"


def record_device_draw_failure(device_id: str, prompt: str, *, error: str = "") -> None:
    """Store a failed draw prompt for later enhance_drawing_prompt retry hints."""
    cleaned = (prompt or "").strip()[:120]
    if not device_id or not cleaned:
        return

    session_id = device_session_id(device_id)
    save_typed_memory(
        DEVICE_DRAW_FAILED,
        summary=cleaned,
        detail=(error or "")[:240],
        session_id=session_id,
    )

    entries = query_by_type(DEVICE_DRAW_FAILED, limit=100, session_id=session_id)
    for entry in entries[_MAX_FAILED:]:
        delete_memory(entry.id)


def list_device_draw_failures(device_id: str, *, limit: int = _MAX_FAILED) -> list[str]:
    """Return recent failed prompts oldest-first (enhancer uses the last item)."""
    if not device_id:
        return []
    entries = query_by_type(
        DEVICE_DRAW_FAILED,
        limit=limit,
        session_id=device_session_id(device_id),
    )
    return [entry.summary for entry in reversed(entries)]


def reset_device_draw_failures(device_id: str | None = None) -> None:
    """Clear persisted draw failures (test isolation)."""
    try:
        if device_id:
            delete_memories_by_type(DEVICE_DRAW_FAILED, session_id=device_session_id(device_id))
        else:
            delete_memories_by_type(DEVICE_DRAW_FAILED)
    except Exception as exc:
        logger.warning("reset_device_draw_failures skipped: %s", exc)
