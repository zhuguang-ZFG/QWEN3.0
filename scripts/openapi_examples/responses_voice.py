"""Voice REST response examples for the public OpenAPI builder."""

from __future__ import annotations

from typing import Any


def _resp_voice_transcribe() -> Any:
    return {
        "text": "画一只猫",
        "intent": "draw_generated",
        "audioId": "aud-00000000-0000-0000-0000-000000000001",
    }


def _resp_voice_ticket() -> Any:
    return {"ticket": "tk-xxxxxxxx", "expires_in": 30}
