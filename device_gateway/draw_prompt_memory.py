"""Draw conversation memory facade.

Thin wrappers over `session_memory.device_draw_memory` so the prompt enhancer
module stays under the 300-line file limit. All functions degrade gracefully
when persistence is unavailable.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MAX_FAILED = 5


def reset_draw_prompt_history_for_tests(device_id: str | None = None) -> None:
    """Clear failed prompt history and conversation turns (test isolation)."""
    try:
        from session_memory.device_draw_memory import reset_device_draw_session

        reset_device_draw_session(device_id)
    except Exception as exc:
        logger.info("draw prompt history reset skipped: %s", exc)


def get_draw_conversation_context(device_id: str | None, current_prompt: str = "") -> str:
    """Return formatted multi-turn draw context for prompt enhancement."""
    if not device_id:
        return ""
    try:
        from session_memory.device_draw_memory import format_device_draw_conversation_context

        return format_device_draw_conversation_context(
            device_id,
            exclude_prompt=(current_prompt or "").strip(),
        )
    except Exception as exc:
        logger.warning("get_draw_conversation_context failed for %s: %s", device_id, exc)
        return ""


def record_device_draw_turn(
    device_id: str | None,
    prompt: str,
    *,
    status: str,
    error: str = "",
) -> None:
    """Persist one draw conversation turn."""
    if not device_id:
        return
    cleaned = (prompt or "").strip()[:120]
    if not cleaned:
        return
    try:
        from session_memory.device_draw_memory import record_device_draw_turn as _record_turn

        _record_turn(device_id, cleaned, status=status, error=error)
    except Exception as exc:
        logger.warning("record_device_draw_turn failed for %s: %s", device_id, exc)


def record_failed_draw_prompt(device_id: str | None, prompt: str, *, error: str = "") -> None:
    """Remember a prompt that failed generation or vectorization for retry hints."""
    if not device_id:
        return
    cleaned = (prompt or "").strip()[:120]
    if not cleaned:
        return
    try:
        from session_memory.device_draw_memory import record_device_draw_failure

        record_device_draw_failure(device_id, cleaned, error=error)
    except Exception as exc:
        logger.warning("record_failed_draw_prompt persistence failed for %s: %s", device_id, exc)


def get_failed_draw_prompts(device_id: str | None) -> list[str]:
    """Return recent failed draw prompts for a device."""
    if not device_id:
        return []
    try:
        from session_memory.device_draw_memory import list_device_draw_failures

        return list_device_draw_failures(device_id, limit=_MAX_FAILED)
    except Exception as exc:
        logger.warning("get_failed_draw_prompts failed for %s: %s", device_id, exc)
        return []
