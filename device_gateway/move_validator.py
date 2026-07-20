"""Point-to-point move validation (GW-R3-12).

move_abs / move_rel carry scalar coordinates (x/y/z, dx/dy/dz) instead of a
path array, so they bypass ``profile_limit_error`` (which only inspects a
``path``). Server-side workspace / jog-step bounds are enforced here before
dispatch; the firmware re-checks against live position as a backstop.

Extracted from path_validator to keep that module under the 300-line gate.
Imports constants + feed parsing from path_validator; path_validator imports
this module lazily (inside validate_capability_params) to avoid an import cycle.
"""

from __future__ import annotations

import math
from typing import Any

from device_gateway.path_validator import (
    MAX_POINT_COORD,
    MAX_REL_STEP,
    MIN_POINT_COORD,
    _parse_feed_value,
)
from device_gateway.protocol_families import MotionErrorCode
from device_intelligence.schemas import DeviceProfile


def _axis_scalar(params: dict, key: str) -> tuple[float | None, str | None]:
    """Parse one move axis scalar. Missing → 0.0; non-numeric/non-finite → error."""
    raw = params.get(key, 0)
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return None, MotionErrorCode.E_BAD_PARAMS.value
    val = float(raw)
    if not math.isfinite(val):
        return None, MotionErrorCode.E_BAD_PARAMS.value
    return val, None


def _validate_move_abs(params: dict, profile: DeviceProfile | None) -> tuple[dict, str | None]:
    """Absolute point-to-point move. Target must be in [0, workspace] per axis.

    move_abs coordinates are scalars, so profile_limit_error (which only
    inspects a ``path`` array) never sees them — server-side bounds are enforced
    here. Without a profile, fall back to the ±500 hard limit that the firmware
    workspace check backstops; z defaults to 0 and is only bounded when
    explicitly supplied (matches firmware has_z semantics — no silent pen-down).
    """
    sanitized: dict[str, Any] = {"source_capability": "move_abs"}
    has_z = "z" in params
    axes = ("x", "y", "z") if has_z else ("x", "y")
    for axis in axes:
        val, err = _axis_scalar(params, axis)
        if err:
            return {}, err
        if val < MIN_POINT_COORD or val > MAX_POINT_COORD:
            return {}, MotionErrorCode.E_BAD_PARAMS.value
        if profile is not None:
            bound = profile.workspace_mm.get(axis) if isinstance(profile.workspace_mm, dict) else None
            if not isinstance(bound, (int, float)) or not math.isfinite(bound):
                return {}, MotionErrorCode.E_BAD_PARAMS.value
            if val < 0 or val > float(bound):
                return {}, MotionErrorCode.E_BAD_PARAMS.value
        sanitized[axis] = val
    feed, feed_error = _parse_feed_value(params.get("feed", 1000.0))
    if feed_error or feed is None:
        return {}, feed_error or MotionErrorCode.E_BAD_PARAMS.value
    sanitized["feed"] = feed
    return sanitized, None


def _validate_move_rel(params: dict) -> tuple[dict, str | None]:
    """Relative jog. Each axis step is limited to [-MAX_REL_STEP, MAX_REL_STEP] mm
    (firmware limit), and at least one axis must be non-zero. Target-in-workspace
    is enforced by the firmware against live position (server cannot know it)."""
    sanitized: dict[str, Any] = {"source_capability": "move_rel"}
    non_zero = False
    for axis in ("dx", "dy", "dz"):
        if axis == "dz" and axis not in params:
            sanitized[axis] = 0.0
            continue
        val, err = _axis_scalar(params, axis)
        if err:
            return {}, err
        if val < -MAX_REL_STEP or val > MAX_REL_STEP:
            return {}, MotionErrorCode.E_BAD_PARAMS.value
        if val != 0:
            non_zero = True
        sanitized[axis] = val
    if not non_zero:
        return {}, MotionErrorCode.E_BAD_PARAMS.value
    feed, feed_error = _parse_feed_value(params.get("feed", 800.0))
    if feed_error or feed is None:
        return {}, feed_error or MotionErrorCode.E_BAD_PARAMS.value
    sanitized["feed"] = feed
    return sanitized, None


def validate_move_params(capability: str, params: dict, profile: DeviceProfile | None) -> tuple[dict, str | None]:
    """Route move_abs / move_rel to their axis validators (GW-R3-12)."""
    if capability == "move_abs":
        return _validate_move_abs(params, profile)
    return _validate_move_rel(params)
