"""Deterministic first-slice device command mapping."""
from __future__ import annotations

from typing import Any


def resolve_direct_device_command(text: str) -> dict[str, Any] | None:
    normalized = (text or "").strip().lower()
    control_map = {
        "归零": "home",
        "回零": "home",
        "home": "home",
        "暂停": "pause",
        "pause": "pause",
        "继续": "resume",
        "resume": "resume",
        "停止": "stop",
        "stop": "stop",
        "设备信息": "get_device_info",
    }
    if normalized in control_map:
        return {"capability": control_map[normalized], "params": {}, "source": "voice"}
    return None


def resolve_voice_task(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    direct = resolve_direct_device_command(stripped)
    if direct:
        return direct
    if stripped.startswith("写") and len(stripped) > 1:
        return {
            "capability": "write_text",
            "params": {"text": stripped[1:].strip() or stripped},
            "source": "voice",
        }
    if stripped.startswith("画") and len(stripped) > 1:
        return {
            "capability": "draw_generated",
            "params": {"prompt": stripped[1:].strip() or stripped},
            "source": "voice",
        }
    return {
        "capability": "write_text",
        "params": {"text": stripped[:40] or "hello"},
        "source": "voice",
    }

