"""Device task model-routing roles for drawing/writing machines."""

from __future__ import annotations

import re
from typing import Any

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "get_device_info"})


def looks_like_svg_path(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped) and stripped[0] in "MmLCcQqHhVvZz" and re.search(r"[-+]?\d", stripped) is not None


def resolve_device_route_policy(voice_task: dict[str, Any]) -> dict[str, Any]:
    capability = str(voice_task.get("capability", ""))
    params = voice_task.get("params", {})
    if not isinstance(params, dict):
        params = {}

    if capability in CONTROL_CAPABILITIES:
        return _policy("device_control", False, "deterministic", "none")
    if capability == "write_text":
        return _policy("device_write", False, "deterministic", "preview_svg")
    if capability == "draw_generated":
        prompt = str(params.get("prompt", ""))
        if looks_like_svg_path(prompt):
            return _policy("device_vector", False, "svg_vector", "preview_svg")
        return _policy("device_draw", True, "image_then_vector", "vector_path")
    if capability == "run_path":
        return _policy("device_vector", False, "provided_path", "preview_svg")
    return _policy("device_unknown", True, "planner_required", "none")


def _policy(route_role: str, model_required: bool, primary_strategy: str, artifact_required: str) -> dict[str, Any]:
    return {
        "route_role": route_role,
        "model_required": model_required,
        "primary_strategy": primary_strategy,
        "artifact_required": artifact_required,
    }
