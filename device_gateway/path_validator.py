"""Device Gateway path validator — validates motion run_path parameters.

Catches bad input at task-creation time (Server side) so invalid tasks
never reach the device. Returns structured error codes matching the
MotionErrorCode enum in protocol_families.py.
"""

from __future__ import annotations

import math
from typing import Any

from device_gateway.model_routing import CONTROL_CAPABILITIES
from device_gateway.path_data import MAX_PATH_POINTS
from device_gateway.protocol_families import MotionErrorCode
from device_intelligence.safety import profile_limit_error
from device_intelligence.schemas import DeviceProfile

MAX_POINT_COORD = 500.0
MIN_POINT_COORD = -500.0
MAX_FEED = 2000.0
MIN_FEED = 1.0

CAPABILITY_PATH_MAP: dict[str, frozenset[str]] = {
    "run_path": frozenset({"path", "feed"}),
    "write_text": frozenset({"path", "feed", "text"}),
    "draw_generated": frozenset({"path", "feed", "prompt"}),
    "handwriting": frozenset({"path", "feed", "text"}),
    # GW-R3-12: point-to-point motion. move_abs positions to an absolute
    # [0, workspace] target; move_rel is a ±1mm-per-axis jog (firmware limit).
    # Coordinates are scalars (x/y/z, dx/dy/dz), not a path array — validated by
    # _validate_move_params, not the path/feed run_path route.
    "move_abs": frozenset({"x", "y"}),
    "move_rel": frozenset({"dx", "dy"}),
    "home": frozenset(),
    "pause": frozenset(),
    "resume": frozenset(),
    "stop": frozenset(),
    "estop": frozenset(),
    "get_device_info": frozenset(),
}

# Capabilities that compute their own motion path from other inputs (text/image).
# For these, `path` is not required at validation time; feed still gets clamped.
_PATH_GENERATING_CAPABILITIES = frozenset({"write_text", "draw_generated", "handwriting"})

# GW-R3-12: point-to-point motion capabilities. Coordinates are scalars, not a
# path array, so they take a dedicated validation route (_validate_move_params)
# with server-side workspace bounds — the firmware also re-checks, but the
# scalar path bypassed profile_limit_error's path-only checks entirely.
_MOVE_CAPABILITIES = frozenset({"move_abs", "move_rel"})

# Firmware limit (motion_executor.cc): move_rel is a jog — each axis step is
# constrained to [-MAX_REL_STEP, MAX_REL_STEP] mm. Reject larger deltas here so
# the caller gets a structured error instead of a firmware-side rejection.
MAX_REL_STEP = 1.0

# Valid route_policy values per Edge-C schema
VALID_ROUTE_ROLES = frozenset({"device_control", "device_write", "device_draw", "device_vector", "device_unknown"})
VALID_PRIMARY_STRATEGIES = frozenset(
    {"deterministic", "image_then_vector", "svg_vector", "provided_path", "planner_required"}
)
VALID_ARTIFACT_REQUIRED = frozenset({"none", "preview_svg", "vector_path"})


def _axis_value_error(val: Any) -> str | None:
    """Return error code if a single axis value is illegal (finite, in ±500)."""
    if not isinstance(val, (int, float)):
        return MotionErrorCode.E_BAD_PARAMS.value
    # AUDIT-10-V1：NaN/Inf 绕过边界校验（IEEE 754 NaN 比较全 False）。
    if not math.isfinite(val):
        return MotionErrorCode.E_BAD_PARAMS.value
    # Absolute hard limit (defense in depth), applied with or without a profile.
    # GW-R3-5 previously clamped no-profile coords to DEFAULT_WORKSPACE_MM
    # (100mm), but real product firmware advertises 300x300x80mm — this pre-check
    # runs before the profile is resolved (device_app_task_create), so it hard-
    # rejected legitimate coords in (100, 300]. Profile-aware [0, workspace]
    # enforcement still happens in profile_limit_error once the profile resolves.
    if val < MIN_POINT_COORD or val > MAX_POINT_COORD:
        return MotionErrorCode.E_BAD_PARAMS.value
    return None


def _path_points_error(path: list) -> str | None:
    for point in path:
        if not isinstance(point, dict):
            return MotionErrorCode.E_BAD_PARAMS.value
        for axis in ("x", "y", "z"):
            err = _axis_value_error(point.get(axis, 0))
            if err:
                return err
    return None


def _parse_feed_value(raw: Any) -> tuple[float | None, str | None]:
    """AUDIT-10-V2 / GW-R3-1: finite feed in [MIN_FEED, MAX_FEED] or error."""
    try:
        feed = float(raw if raw is not None else 500.0)
    except (TypeError, ValueError):
        return None, MotionErrorCode.E_BAD_PARAMS.value
    if not math.isfinite(feed) or feed < MIN_FEED or feed > MAX_FEED:
        return None, MotionErrorCode.E_BAD_PARAMS.value
    return feed, None


def validate_run_path_params(params: dict, profile: DeviceProfile | None = None) -> tuple[dict, str | None]:
    """Validate motion task run_path parameters.

    Returns (sanitized_params, None) on success or ({}, error_code) on failure.
    The error_code is a MotionErrorCode string value ready for the failure event.
    """
    if not isinstance(params, dict):
        return {}, MotionErrorCode.E_BAD_PARAMS.value
    profile_error = profile_limit_error(params, profile)
    if profile_error:
        return {}, profile_error

    path = params.get("path")
    if not isinstance(path, list) or len(path) == 0:
        return {}, MotionErrorCode.E_MISSING_PATH.value
    if len(path) > MAX_PATH_POINTS:
        return {}, MotionErrorCode.E_BAD_PARAMS.value
    point_error = _path_points_error(path)
    if point_error:
        return {}, point_error
    feed, feed_error = _parse_feed_value(params.get("feed", 500.0))
    if feed_error or feed is None:
        return {}, feed_error or MotionErrorCode.E_BAD_PARAMS.value

    return {
        "path": path,
        "feed": feed,
        "source_capability": str(params.get("source_capability", "unknown")),
    }, None


def _has_draw_image_ref(params: dict) -> bool:
    return bool(
        params.get("image_url")
        or params.get("imageUrl")
        or params.get("gallery_image_id")
        or params.get("galleryImageId")
    )


def _required_fields_present(capability: str, required: tuple | list | set, params: dict) -> str | None:
    for field in required:
        if field in ("path", "feed"):
            continue  # path may be generated later; feed already clamped
        if capability == "draw_generated" and field == "prompt":
            if _has_draw_image_ref(params) and field in params:
                continue
        if field not in params or not params[field]:
            return MotionErrorCode.E_BAD_PARAMS.value
    return None


def _copy_scalar_params(params: dict, sanitized: dict[str, Any]) -> None:
    for key, value in params.items():
        if key in ("path", "feed") or key.startswith("_"):
            continue
        if isinstance(value, str):
            limit = 8192 if key == "preview_svg" else 120
            sanitized[key] = value[:limit]
        elif isinstance(value, (int, float)):
            sanitized[key] = value


def validate_capability_params(
    capability: str,
    params: dict,
    profile: DeviceProfile | None = None,
) -> tuple[dict, str | None]:
    """Validate that the given capability's required params are present.

    Returns (sanitized_params, None) on success or ({}, error_code) on failure.
    """
    required = CAPABILITY_PATH_MAP.get(capability)
    if required is None:
        return {}, MotionErrorCode.E_UNSUPPORTED_CAPABILITY.value

    if capability in CONTROL_CAPABILITIES:
        return {
            "source_capability": str(params.get("source_capability", capability)),
        }, None

    if capability in _MOVE_CAPABILITIES:
        # Lazy import breaks the cycle: move_validator imports coord constants
        # and _parse_feed_value from this module (GW-R3-12 size-gate split).
        from device_gateway.move_validator import validate_move_params

        return validate_move_params(capability, params, profile)

    if capability in _PATH_GENERATING_CAPABILITIES:
        sanitized: dict[str, Any] = {
            "feed": _clamp_feed_value(params.get("feed")),
            "source_capability": str(params.get("source_capability", capability)),
        }
        # GW-B1: generated paths are normalized to the resolved profile
        # workspace upstream (_normalize_generated_path), so profile workspace
        # enforcement now applies to them too — no more "generator honesty"
        # exemption that let 183mm text through a 60mm workspace check.
        path_error = _maybe_preserve_path(params, profile, sanitized)
        if path_error:
            return {}, path_error
    else:
        sanitized, error = validate_run_path_params(params, profile=profile)
        if error:
            return {}, error

    missing = _required_fields_present(capability, required, params)
    if missing:
        return {}, missing
    _copy_scalar_params(params, sanitized)
    return sanitized, None


def _maybe_preserve_path(
    params: dict,
    profile: DeviceProfile | None,
    sanitized: dict[str, Any],
) -> str | None:
    """Validate and preserve an already-generated motion path, if present.

    Returns an error code when the path is invalid; otherwise None.
    """
    path = params.get("path")
    if not isinstance(path, list) or len(path) == 0:
        return None
    validated_path, path_error = validate_run_path_params(params, profile=profile)
    if path_error:
        return path_error
    sanitized["path"] = validated_path["path"]
    return None


def _clamp_feed_value(raw_feed: Any) -> float:
    """Clamp feed to [MIN_FEED, MAX_FEED] with a safe default."""
    try:
        feed = float(raw_feed) if raw_feed is not None else 500.0
    except (TypeError, ValueError):
        feed = 500.0
    # IEEE NaN fails all comparisons, so max/min would silently stick on bounds.
    if not math.isfinite(feed):
        feed = 500.0
    return max(MIN_FEED, min(MAX_FEED, feed))


def validate_route_policy(route_policy: dict, capability: str = "") -> tuple[dict, str | None]:
    """Validate route_policy against Edge-C schema constraints.

    Returns (route_policy, None) on success or ({}, error_code) on failure.
    Catches unknown route roles, invalid strategies, and firmware-incompatible
    combinations before the task reaches the device.
    """
    if not isinstance(route_policy, dict):
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    route_role = str(route_policy.get("route_role", ""))
    primary_strategy = str(route_policy.get("primary_strategy", ""))
    artifact_required = str(route_policy.get("artifact_required", ""))

    if route_role not in VALID_ROUTE_ROLES:
        return {}, MotionErrorCode.E_UNSUPPORTED_CAPABILITY.value

    if primary_strategy not in VALID_PRIMARY_STRATEGIES:
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    if artifact_required not in VALID_ARTIFACT_REQUIRED:
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    # Firmware-incompatible combinations:
    # device_control should never require a model
    if route_role == "device_control" and route_policy.get("model_required", False):
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    # device_control should use deterministic strategy
    if route_role == "device_control" and primary_strategy != "deterministic":
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    # device_draw must require a model (image_then_vector needs AI)
    if route_role == "device_draw" and not route_policy.get("model_required", False):
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    # device_draw must use image_then_vector
    if route_role == "device_draw" and primary_strategy != "image_then_vector":
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    # device_unknown must require planner
    if route_role == "device_unknown" and primary_strategy != "planner_required":
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    return route_policy, None
