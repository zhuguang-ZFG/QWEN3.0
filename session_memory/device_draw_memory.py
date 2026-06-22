"""Persist device draw failure prompts and multi-turn conversation in session_memory."""

from __future__ import annotations

import logging

from session_memory.store import delete_memories_by_type, delete_memory, query_by_type, save_typed_memory

logger = logging.getLogger(__name__)

DEVICE_DRAW_FAILED = "device_draw_failed"
DEVICE_DRAW_TURN = "device_draw_turn"
_MAX_FAILED = 5
_MAX_TURNS = 8
_MAX_CONTEXT_TURNS = 3


def device_session_id(device_id: str) -> str:
    """Scope draw memories to a stable device session key."""
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


def record_device_draw_turn(device_id: str, prompt: str, *, status: str, error: str = "") -> None:
    """Store one draw conversation turn for multi-turn prompt context."""
    cleaned = (prompt or "").strip()[:120]
    if not device_id or not cleaned:
        return

    detail = status if not error else f"{status}:{error[:200]}"
    session_id = device_session_id(device_id)
    save_typed_memory(
        DEVICE_DRAW_TURN,
        summary=cleaned,
        detail=detail[:240],
        session_id=session_id,
    )

    entries = query_by_type(DEVICE_DRAW_TURN, limit=100, session_id=session_id)
    for entry in entries[_MAX_TURNS:]:
        delete_memory(entry.id)


def format_device_draw_conversation_context(
    device_id: str,
    *,
    limit: int = _MAX_CONTEXT_TURNS,
    exclude_prompt: str = "",
) -> str:
    """Build recent draw-turn context for prompt injection (oldest first)."""
    if not device_id:
        return ""

    entries = query_by_type(
        DEVICE_DRAW_TURN,
        limit=max(limit, _MAX_CONTEXT_TURNS) + 1,
        session_id=device_session_id(device_id),
    )
    if not entries:
        return ""

    exclude = (exclude_prompt or "").strip()
    lines: list[str] = []
    for entry in reversed(entries):
        if exclude and entry.summary == exclude:
            continue
        status = (entry.detail or "success").split(":", 1)[0]
        lines.append(f"- {entry.summary} [{status}]")
        if len(lines) >= limit:
            break

    if not lines:
        return ""
    return "近期绘图对话：\n" + "\n".join(lines)


def reset_device_draw_failures(device_id: str | None = None) -> None:
    """Clear persisted draw failures (test isolation)."""
    _reset_memory_type(DEVICE_DRAW_FAILED, device_id)


def reset_device_draw_turns(device_id: str | None = None) -> None:
    """Clear persisted draw turns (test isolation)."""
    _reset_memory_type(DEVICE_DRAW_TURN, device_id)


def reset_device_draw_session(device_id: str | None = None) -> None:
    """Clear failures and conversation turns for a device session."""
    reset_device_draw_failures(device_id)
    reset_device_draw_turns(device_id)


def _reset_memory_type(memory_type: str, device_id: str | None) -> None:
    try:
        if device_id:
            delete_memories_by_type(memory_type, session_id=device_session_id(device_id))
        else:
            delete_memories_by_type(memory_type)
    except Exception as exc:
        logger.warning("reset %s skipped: %s", memory_type, exc)
