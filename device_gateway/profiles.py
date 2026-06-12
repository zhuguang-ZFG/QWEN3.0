"""Device profile routing inputs — first-class routing decisions from hardware profiles.

Phase 3: route decisions account for firmware, hardware, workspace, and point
limits before model selection.

Missing profile data is treated conservatively: lower point count, smaller
scale, preset routes preferred, generated drawing downgraded or approval-gated.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from device_gateway.device_profile import DeviceProfile
from device_gateway.device_simplification_logger import record_simplification
from device_intelligence.schemas import DEFAULT_WORKSPACE_MM

_log = logging.getLogger(__name__)

# ── Conservative defaults for missing profile data ─────────────────────────

CONSERVATIVE_MAX_PATH_POINTS = 50
CONSERVATIVE_MAX_FEED = 600.0
CONSERVATIVE_WORKSPACE_MM = {"x": 60.0, "y": 60.0, "z": 10.0}

# ── Known device profiles ─────────────────────────────────────────────────

KNOWN_PROFILES: dict[str, DeviceProfile] = {}


def register_profile(profile: DeviceProfile) -> None:
    """Register a known device profile by profile_id."""
    KNOWN_PROFILES[profile.profile_id] = profile


def get_profile(profile_id: str) -> DeviceProfile | None:
    """Look up a registered device profile."""
    return KNOWN_PROFILES.get(profile_id)


def resolve_profile(
    *,
    profile_id: str = "",
    device_id: str = "",
    fw_rev: str = "",
    hw_rev: str = "",
    shadow_profile: dict[str, Any] | None = None,
) -> ResolvedProfile:
    """Resolve a device profile for routing decisions.

    Priority:
    1. Registered profile by profile_id
    2. Shadow store profile data
    3. Conservative defaults (missing data = safe fallback)

    Returns a ResolvedProfile with routing hints and completeness flag.
    """
    profile = get_profile(profile_id) if profile_id else None
    complete = profile is not None

    if profile is None and shadow_profile:
        profile = _profile_from_shadow(shadow_profile, profile_id or device_id)

    if profile is None:
        profile = _conservative_profile(device_id or "unknown")

    fw_compatible = _check_fw_compatibility(profile, fw_rev)
    routing_hints = _compute_routing_hints(profile, complete, fw_compatible)

    return ResolvedProfile(
        profile=profile,
        complete=complete,
        fw_compatible=fw_compatible,
        routing_hints=routing_hints,
    )


def apply_profile_constraints(
    task: dict[str, Any],
    resolved: ResolvedProfile,
) -> dict[str, Any]:
    """Apply profile constraints to a task's route_policy and metadata.

    - Downgrades draw_generated to approval-gated when profile is incomplete.
    - Caps path points and feed to profile limits.
    - Adds profile routing metadata to the task.
    - Records simplification decisions for audit trail.
    """
    original_task = json.loads(json.dumps(task))
    simplifications: list[str] = []

    if not resolved.complete and task.get("route_policy", {}).get("model_required"):
        policy = dict(task.get("route_policy", {}))
        policy["approval_required"] = True
        policy["approval_reason"] = "incomplete device profile"
        task["route_policy"] = policy
        simplifications.append("approval_gate:incomplete_profile")

    # Cap path points if task has path data
    params = task.get("params", {})
    if isinstance(params, dict) and "path" in params:
        path = params.get("path", [])
        if isinstance(path, list) and len(path) > resolved.profile.max_path_points:
            params["path"] = path[:resolved.profile.max_path_points]
            task["params"] = params
            simplifications.append(f"cap_path_points:{len(path)}→{resolved.profile.max_path_points}")

    # Cap feed rate if exceeds profile limit
    if isinstance(params, dict):
        feed = params.get("feed")
        if isinstance(feed, (int, float)) and feed > resolved.profile.max_feed:
            params["feed"] = resolved.profile.max_feed
            task["params"] = params
            simplifications.append(f"cap_feed:{feed}→{resolved.profile.max_feed}")

    # Record simplification if any changes were made
    if simplifications:
        constrained_task = json.loads(json.dumps(task))
        record_simplification(
            device_id=str(task.get("device_id", "")),
            task_id=str(task.get("task_id", "")),
            simplification_type=";".join(simplifications),
            reason=f"profile_constraints:complete={resolved.complete},fw_compatible={resolved.fw_compatible}",
            original=original_task,
            constrained=constrained_task,
        )

    task["profile_routing"] = {
        "profile_id": resolved.profile.profile_id,
        "complete": resolved.complete,
        "fw_compatible": resolved.fw_compatible,
        "max_path_points": resolved.profile.max_path_points,
        "max_feed": resolved.profile.max_feed,
    }
    task["profile_routing"].update(resolved.routing_hints)
    return task


# ── Data classes ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResolvedProfile:
    """A resolved device profile with routing metadata."""

    profile: DeviceProfile
    complete: bool
    fw_compatible: bool
    routing_hints: dict[str, Any] = field(default_factory=dict)


# ── Internal helpers ───────────────────────────────────────────────────────


def _conservative_profile(device_id: str) -> DeviceProfile:
    return DeviceProfile(
        device_id=device_id,
        profile_id=f"conservative-{device_id}",
        model="unknown",
        workspace_mm=dict(CONSERVATIVE_WORKSPACE_MM),
        max_feed=CONSERVATIVE_MAX_FEED,
        max_path_points=CONSERVATIVE_MAX_PATH_POINTS,
        capabilities=("home", "pause", "resume", "run_path", "stop"),
        supported_fw_prefixes=("",),
        profile_version="0",
        fw_rev="",
        u1_fw_rev="",
        hw_rev="",
        limits={"max_points": CONSERVATIVE_MAX_PATH_POINTS},
    )


def _profile_from_shadow(shadow: dict[str, Any], fallback_id: str) -> DeviceProfile | None:
    """Try to build a DeviceProfile from shadow store data."""
    workspace = shadow.get("workspace_mm")
    if not isinstance(workspace, dict):
        workspace = None
    max_feed = shadow.get("max_feed")
    max_points = shadow.get("max_path_points")
    capabilities = shadow.get("capabilities")
    fw_prefixes = shadow.get("supported_fw_prefixes")

    if not any([workspace, max_feed, max_points]):
        return None

    try:
        return DeviceProfile(
            device_id=str(fallback_id),
            profile_id=str(shadow.get("profile_id", fallback_id)),
            model=str(shadow.get("model", "shadow")),
            workspace_mm=workspace if isinstance(workspace, dict) else dict(DEFAULT_WORKSPACE_MM),
            max_feed=float(max_feed) if isinstance(max_feed, (int, float)) and max_feed > 0 else 1200.0,
            max_path_points=int(max_points) if isinstance(max_points, int) and max_points > 0 else 200,
            capabilities=tuple(capabilities) if isinstance(capabilities, (list, tuple)) else ("run_path",),
            supported_fw_prefixes=tuple(fw_prefixes) if isinstance(fw_prefixes, (list, tuple)) else ("",),
            profile_version="1",
            fw_rev=str(shadow.get("fw_rev", "")),
            u1_fw_rev=str(shadow.get("u1_fw_rev", "")),
            hw_rev=str(shadow.get("hw_rev", "")),
            limits={"max_points": int(max_points) if isinstance(max_points, int) and max_points > 0 else 200},
        )
    except (ValueError, TypeError):
        _log.debug("shadow profile build failed for device=%s", fallback_id)
        return None


def _check_fw_compatibility(profile: DeviceProfile, fw_rev: str) -> bool:
    """Check if firmware revision is compatible with the profile."""
    if not fw_rev:
        return True  # unknown fw is accepted conservatively
    prefixes = profile.supported_fw_prefixes
    if "" in prefixes:
        return True
    return any(fw_rev.startswith(p) for p in prefixes)


def _compute_routing_hints(
    profile: DeviceProfile,
    complete: bool,
    fw_compatible: bool,
) -> dict[str, Any]:
    """Compute routing hints based on profile and completeness."""
    hints: dict[str, Any] = {
        "prefer_preset": not complete,
        "max_complexity": "simple" if profile.max_path_points <= CONSERVATIVE_MAX_PATH_POINTS else "normal",
    }
    if not complete:
        hints["downgrade_generated"] = True
    if not fw_compatible:
        hints["block_dispatch"] = True
        hints["block_reason"] = "firmware incompatible"
    return hints


# ── Module reset (for tests) ──────────────────────────────────────────────


def reset_profiles_for_tests() -> None:
    KNOWN_PROFILES.clear()
