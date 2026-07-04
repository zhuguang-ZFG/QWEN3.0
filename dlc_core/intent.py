"""Intent parsing facade for DLC core."""

from __future__ import annotations

from typing import Any

from device_gateway.intent import resolve_voice_task as _resolve_voice_task


def parse_intent(text: str) -> dict[str, Any]:
    """Parse a natural-language command into a structured device intent.

    Returns:
        {"capability": "write_text" | "draw_generated" | ..., "params": {...},
         "source": "voice", "explanation": "..."}
    """
    return _resolve_voice_task(text)
