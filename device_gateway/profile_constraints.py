"""Apply device profile constraints to a task's route_policy and metadata.

Extracted from ``device_gateway.profiles`` (Q batch deep-slim) so that
``profiles.py`` owns profile *resolution* (registry + ``resolve_profile`` +
routing hints) while this module owns profile *constraint application*
(gating, capping, simplification recording). Pure functions; no socket or
FastAPI coupling. ``ResolvedProfile`` is imported under ``TYPE_CHECKING``
only to avoid a circular runtime import back into ``profiles``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from device_gateway.device_write_handler import record_simplification

if TYPE_CHECKING:
    from device_gateway.profiles import ResolvedProfile


def _apply_approval_gate(task: dict[str, Any], resolved: ResolvedProfile) -> str | None:
    if not resolved.complete and task.get("route_policy", {}).get("model_required"):
        policy = dict(task.get("route_policy", {}))
        if not policy.get("approval_required"):
            policy["approval_required"] = True
            policy["approval_reason"] = "incomplete device profile"
            task["route_policy"] = policy
        return "approval_gate:incomplete_profile"
    return None


def _cap_param(task: dict[str, Any], key: str, limit: float | int) -> str | None:
    """Cap a numeric task param to a profile limit. Returns simplification note or None."""
    params = task.get("params", {})
    if not isinstance(params, dict):
        return None
    value = params.get(key)
    if isinstance(value, (int, float)) and value > limit:
        params[key] = limit
        task["params"] = params
        return f"cap_{key}:{value}→{limit}"
    return None


def apply_profile_constraints(
    task: dict[str, Any],
    resolved: ResolvedProfile,
) -> dict[str, Any]:
    """Apply profile constraints to a task's route_policy and metadata."""
    original_task = json.loads(json.dumps(task))
    simplifications: list[str] = []

    gate = _apply_approval_gate(task, resolved)
    if gate:
        simplifications.append(gate)

    # Cap path points if task has path data
    params = task.get("params", {})
    if isinstance(params, dict) and "path" in params:
        path = params.get("path", [])
        if isinstance(path, list) and len(path) > resolved.profile.max_path_points:
            params["path"] = path[: resolved.profile.max_path_points]
            task["params"] = params
            simplifications.append(f"cap_path_points:{len(path)}→{resolved.profile.max_path_points}")

    for note in (_cap_param(task, "feed", resolved.profile.max_feed),):
        if note:
            simplifications.append(note)

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
