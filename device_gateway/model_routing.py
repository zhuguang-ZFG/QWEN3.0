"""Device task model-routing roles for drawing/writing machines."""

from __future__ import annotations

import re
from typing import Any

from device_gateway.device_profile import DeviceProfile
from device_gateway.profiles import ResolvedProfile, enrich_route_policy_with_profile, resolve_profile

from .artifact_recorder import record_route_evidence
from .model_routing_selection import (
    MODEL_REGISTRY,
    _TIER_ORDER,
    _adjust_weight_for_preferences,
    _build_selection_result,
    _filter_compatible_models,
    select_model_with_profile,
)

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "estop", "get_device_info"})

# ── Device role routing preferences ─────────────────────────────────────────
#
# Maps route_role to preferred backends in priority order.
# These are the admitted backends for each device role per the admission report.

DEVICE_ROLE_PREFERENCES: dict[str, list[dict[str, Any]]] = {
    "device_control": [
        {"backend": "deterministic", "reason": "本地确定性解析器，无 LLM 依赖"},
    ],
    "device_write": [
        {"backend": "deterministic", "reason": "本地确定性渲染器，文字转路径"},
    ],
    "device_draw": [
        {"backend": "dashscope_wanx", "reason": "阿里云 Wanx 图生 API，已验证"},
        {"backend": "dashscope_flux", "reason": "阿里云 Flux 图生 API，备选"},
    ],
    "device_vector": [
        {"backend": "opencv_contour", "reason": "本地 OpenCV 轮廓检测，确定性"},
    ],
    "device_unknown": [
        {"backend": "deterministic", "reason": "确定性解析器回退"},
    ],
}


def looks_like_svg_path(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped) and stripped[0] in "MmLCcQqHhVvZz" and re.search(r"[-+]?\d", stripped) is not None


def get_preferred_backend(route_role: str) -> dict[str, Any] | None:
    """Get the preferred backend for a device route role.

    Returns the first admitted backend for the role, or None if no preference.
    """
    prefs = DEVICE_ROLE_PREFERENCES.get(route_role, [])
    return prefs[0] if prefs else None


def get_route_role_alternatives(route_role: str) -> list[dict[str, Any]]:
    """Get all admitted backends for a device route role (for fallback)."""
    return DEVICE_ROLE_PREFERENCES.get(route_role, [])


def resolve_device_route_policy(
    voice_task: dict[str, Any],
    device_id: str = "",
    *,
    profile_id: str = "",
    fw_rev: str = "",
    shadow_profile: dict[str, Any] | None = None,
    resolved_profile: ResolvedProfile | None = None,
) -> dict[str, Any]:
    capability = str(voice_task.get("capability", ""))
    params = voice_task.get("params", {})
    if not isinstance(params, dict):
        params = {}

    if capability in CONTROL_CAPABILITIES:
        policy = _policy("device_control", False, "deterministic", "none")
    elif capability == "write_text":
        policy = _policy("device_write", False, "deterministic", "preview_svg")
    elif capability == "draw_generated":
        prompt = str(params.get("prompt", ""))
        if looks_like_svg_path(prompt):
            policy = _policy("device_vector", False, "svg_vector", "preview_svg")
        else:
            policy = _policy("device_draw", True, "image_then_vector", "vector_path")
    elif capability == "run_path":
        policy = _policy("device_vector", False, "provided_path", "preview_svg")
    else:
        policy = _policy("device_unknown", True, "planner_required", "none")

    preferred = get_preferred_backend(policy["route_role"])
    policy["backend"] = preferred["backend"] if preferred else ""

    resolved = resolved_profile
    if resolved is None and (device_id or profile_id or fw_rev or shadow_profile):
        resolved = resolve_profile(
            profile_id=profile_id or str(voice_task.get("profile_id", "") or ""),
            device_id=device_id,
            fw_rev=fw_rev or str(voice_task.get("fw_rev", "") or ""),
            shadow_profile=shadow_profile
            if shadow_profile is not None
            else (voice_task.get("shadow_profile") if isinstance(voice_task.get("shadow_profile"), dict) else None),
        )
    if resolved is not None:
        policy = enrich_route_policy_with_profile(policy, capability, resolved)

    if device_id:
        profile_note = ""
        if resolved is not None:
            profile_note = f",profile_complete={resolved.complete}"
        record_route_evidence(
            device_id=device_id,
            task_id="",
            route_policy=policy,
            backend=policy["backend"],
            reason=f"capability={capability}{profile_note}",
        )

    return policy


def _policy(
    route_role: str, model_required: bool, primary_strategy: str, artifact_required: str, backend: str = ""
) -> dict[str, Any]:
    return {
        "route_role": route_role,
        "model_required": model_required,
        "primary_strategy": primary_strategy,
        "artifact_required": artifact_required,
        "backend": backend,
    }


__all__ = [
    "CONTROL_CAPABILITIES",
    "DEVICE_ROLE_PREFERENCES",
    "MODEL_REGISTRY",
    "_TIER_ORDER",
    "_adjust_weight_for_preferences",
    "_build_selection_result",
    "_filter_compatible_models",
    "_policy",
    "get_preferred_backend",
    "get_route_role_alternatives",
    "looks_like_svg_path",
    "resolve_device_route_policy",
    "select_model_with_profile",
]
