"""Model selection logic for device task model-routing."""

from __future__ import annotations

from typing import Any

from device_gateway.device_profile import DevicePreferences, DeviceProfile

_TIER_ORDER = {"fast": 0, "balanced": 1, "quality": 2}

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
            weight=weight,
            tier=entry.get("tier", "balanced"),
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
            "selected_model": "",
            "backend": "",
            "tier": "",
            "weight": 0,
            "alternatives": [],
            "reason": "no compatible model for device profile",
        }
    best_weight, best_entry = compatible[0]
    alternatives = [
        {"model": entry["name"], "backend": entry.get("backend", ""), "weight": w} for w, entry in compatible[1:]
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
