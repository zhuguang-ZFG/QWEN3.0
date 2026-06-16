"""Device task model-routing roles for drawing/writing machines."""

from __future__ import annotations

import re
from typing import Any

from device_gateway.device_profile import DevicePreferences, DeviceProfile
from device_gateway.profiles import ResolvedProfile, enrich_route_policy_with_profile, resolve_profile

from .artifact_recorder import record_route_evidence

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "estop", "get_device_info"})

# ── Model/backend registry (tiered) ────────────────────────────────────────
#
# Each entry describes a backend model that can be selected for a task.
# ``tier`` controls ordering (fast → cheap → quality).
# ``requirement`` defines minimum device capability to run this model.

MODEL_REGISTRY: list[dict[str, Any]] = [
    # Fast tier (low compute, high latency sensitivity)
    {
        "name": "scnet_ds_flash",
        "backend": "scnet_ds",
        "tier": "fast",
        "default_weight": 10,
        "requirement": {
            "min_compute_level": "low",
            "min_memory_mb": 128,
            "requires_features": ["text"],
        },
    },
    {
        "name": "scnet_ds_medium",
        "backend": "scnet_ds",
        "tier": "fast",
        "default_weight": 8,
        "requirement": {
            "min_compute_level": "low",
            "min_memory_mb": 256,
            "requires_features": ["text", "vector_path"],
        },
    },
    # Balanced tier
    {
        "name": "scnet_large",
        "backend": "scnet_large",
        "tier": "balanced",
        "default_weight": 5,
        "requirement": {
            "min_compute_level": "medium",
            "min_memory_mb": 512,
            "requires_features": ["text", "vector_path"],
        },
    },
    # Quality tier (high compute, high quality)
    {
        "name": "github_gpt4o",
        "backend": "github_openai",
        "tier": "quality",
        "default_weight": 3,
        "requirement": {
            "min_compute_level": "high",
            "min_memory_mb": 1024,
            "requires_features": ["text", "vector_path", "vision"],
        },
    },
    {
        "name": "gemini_2p5_pro",
        "backend": "google_gemini",
        "tier": "quality",
        "default_weight": 3,
        "requirement": {
            "min_compute_level": "high",
            "min_memory_mb": 1024,
            "requires_features": ["text", "vector_path", "vision"],
        },
    },
]

_TIER_ORDER = {"fast": 0, "balanced": 1, "quality": 2}

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


def _filter_compatible_models(
    device_profile: DeviceProfile,
) -> list[tuple[int, dict[str, Any]]]:
    """Filter and weight models compatible with a device profile."""
    compatible: list[tuple[int, dict[str, Any]]] = []
    for entry in MODEL_REGISTRY:
        req = entry.get("requirement", {})
        if not device_profile.capability.is_compatible(req):
            continue
        backend = entry.get("backend", "")
        if backend in device_profile.history.failed_backends:
            continue
        weight = entry.get("default_weight", 5)
        weight = _adjust_weight_for_preferences(
            weight=weight, tier=entry.get("tier", "balanced"),
            prefs=device_profile.preferences,
        )
        if entry["name"] in device_profile.history.preferred_models:
            weight += 3
        compatible.append((weight, entry))
    compatible.sort(key=lambda x: (-x[0], _TIER_ORDER.get(x[1].get("tier", "balanced"), 99)))
    return compatible


def _build_selection_result(compatible: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    """Build selection result dict from ranked compatible models."""
    if not compatible:
        return {
            "selected_model": "", "backend": "", "tier": "",
            "weight": 0, "alternatives": [],
            "reason": "no compatible model for device profile",
        }
    best_weight, best_entry = compatible[0]
    alternatives = [
        {"model": entry["name"], "backend": entry.get("backend", ""), "weight": w}
        for w, entry in compatible[1:]
    ]
    return {
        "selected_model": best_entry["name"],
        "backend": best_entry.get("backend", ""),
        "tier": best_entry.get("tier", ""),
        "weight": best_weight,
        "alternatives": alternatives,
        "reason": f"compatible={len(compatible)} candidates; best tier={best_entry.get('tier')} weight={best_weight}",
    }


def select_model_with_profile(
    device_profile: DeviceProfile,
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select the best model/backend given a device profile and task context.

    Steps:
    1. Filter the MODEL_REGISTRY by device capability (compute, memory, features).
    2. Exclude backends that appear in ``device_profile.history.failed_backends``.
    3. Adjust routing weights based on preferences.
    4. Rank by adjusted weight and return the top candidate.

    Returns a dict with keys:
      selected_model  — model name or empty string if none compatible
      backend         — backend identifier
      tier            — the tier of the selected model
      weight          — final adjusted weight
      alternatives    — list of compatible alternatives with their weights
      reason          — human-readable selection rationale
    """
    compatible = _filter_compatible_models(device_profile)
    return _build_selection_result(compatible)


def _adjust_weight_for_preferences(
    weight: int,
    tier: str,
    prefs: DevicePreferences,
) -> int:
    """Adjust a model's weight based on device preferences."""
    adjusted = weight

    if prefs.latency_sensitive:
        if tier == "fast":
            adjusted += 8
        elif tier == "balanced":
            adjusted += 2
        elif tier == "quality":
            adjusted -= 5

    if prefs.quality_priority == "speed":
        if tier == "fast":
            adjusted += 4
        elif tier == "quality":
            adjusted -= 3
    elif prefs.quality_priority == "quality":
        if tier == "quality":
            adjusted += 6
        elif tier == "fast":
            adjusted -= 3
    # "balanced" — no adjustment

    if prefs.cost_sensitivity == "high":
        if tier == "quality":
            adjusted -= 4
        elif tier == "fast":
            adjusted += 2
    elif prefs.cost_sensitivity == "medium":
        if tier == "quality":
            adjusted -= 2

    return max(adjusted, 1)  # never drop below 1


def _policy(route_role: str, model_required: bool, primary_strategy: str,
            artifact_required: str, backend: str = "") -> dict[str, Any]:
    return {
        "route_role": route_role,
        "model_required": model_required,
        "primary_strategy": primary_strategy,
        "artifact_required": artifact_required,
        "backend": backend,
    }
