"""Device task model-routing roles for drawing/writing machines."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Awaitable, Callable, TypeVar

_log = logging.getLogger(__name__)
T = TypeVar("T")

from device_gateway.profiles import ResolvedProfile, enrich_route_policy_with_profile, resolve_profile

from .task_recorder import record_route_evidence
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


def _auto_fallback_enabled() -> bool:
    """Return True when *LIMA_AUTO_FALLBACK* is set to a truthy value."""
    return os.environ.get("LIMA_AUTO_FALLBACK", "0").strip().lower() in {"1", "true", "on", "yes"}


def _should_continue_fallback(
    *,
    enabled: bool,
    idempotent: bool,
    route_role: str,
    backend: dict[str, Any],
    exc: BaseException,
) -> bool:
    """Return True when the next backend should be tried; raise otherwise."""
    if not enabled:
        raise exc
    if not idempotent:
        _log.warning(
            "fallback stop (non-idempotent) role=%s backend=%s: %s",
            route_role,
            backend.get("backend"),
            type(exc).__name__,
        )
        raise exc
    _log.warning(
        "fallback continue role=%s backend=%s -> next: %s",
        route_role,
        backend.get("backend"),
        type(exc).__name__,
    )
    return True


async def try_backends(
    route_role: str,
    execute_fn: Callable[[dict[str, Any]], Awaitable[T]],
    *,
    idempotent: bool = False,
    timeout: float = 30.0,
) -> T:
    """Try each backend for *route_role* in priority order, returning the first success.

    Fallback requires both ``LIMA_AUTO_FALLBACK`` truthy and ``idempotent=True``.
    Non-idempotent failures re-raise immediately. Every failed attempt logs a warning.
    """
    alts = get_route_role_alternatives(route_role)
    if not alts:
        raise ValueError(f"no backends for route_role={route_role!r}")

    enabled = _auto_fallback_enabled()
    last_exc: BaseException | None = None
    for backend in alts:
        try:
            return await asyncio.wait_for(execute_fn(backend), timeout=timeout)
        except Exception as exc:
            last_exc = exc
            _should_continue_fallback(
                enabled=enabled,
                idempotent=idempotent,
                route_role=route_role,
                backend=backend,
                exc=exc,
            )

    assert last_exc is not None  # alts is non-empty
    raise last_exc  # type: ignore[misc]


def _classify_capability(capability: str, params: dict) -> dict[str, Any]:
    """Map a device capability to a base route_policy."""
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
    # GW-R3-12: point-to-point motion is deterministic and needs no model —
    # same route class as control commands (validate_route_policy requires
    # device_control to be deterministic + model-free, which move satisfies).
    if capability in ("move_abs", "move_rel"):
        return _policy("device_control", False, "deterministic", "none")
    return _policy("device_unknown", True, "planner_required", "none")


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

    policy = _classify_capability(capability, params)

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
    "try_backends",
]
