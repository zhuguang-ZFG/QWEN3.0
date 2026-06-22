"""Resolve draw prompt context from device profile and failure history."""

from __future__ import annotations

import logging

from device_gateway.device_profile.registry import get_device_profile
from device_gateway.draw_prompt_enhancer import CAPABILITY_PROMPT_MAP

logger = logging.getLogger(__name__)

_MAX_FAILED = 5

_WRITING_HINTS = ("writing", "write", "u8", "写字", "书写机")
_PLOTTER_HINTS = ("plotter", "xy", "draw", "u1", "笔绘")


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


def resolve_device_type(device_id: str | None, prefs: dict) -> str:
    """Map device profile / prefs to draw_prompt_enhancer device_type key."""
    explicit = prefs.get("device_type")
    if isinstance(explicit, str) and explicit in CAPABILITY_PROMPT_MAP:
        return explicit

    profile = get_device_profile(device_id) if device_id else None
    if profile is None:
        return "esp32_xy_plotter"

    combined = f"{profile.model} {profile.profile_id}".lower()
    if any(hint in combined for hint in _WRITING_HINTS):
        return "esp32_writing_machine"
    if any(hint in combined for hint in _PLOTTER_HINTS):
        return "esp32_xy_plotter"

    features = set(profile.capability.supported_features)
    if "text" in features and "vector_path" not in features:
        return "esp32_writing_machine"
    return "esp32_xy_plotter"
