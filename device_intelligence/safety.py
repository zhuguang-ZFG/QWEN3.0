"""Profile-aware safety validation for device motion tasks."""

from __future__ import annotations

import math
from typing import Any

from device_gateway.protocol_families import MotionErrorCode

from .schemas import DeviceProfile


def validate_profile_compatibility(profile: DeviceProfile, fw_rev: str) -> str | None:
    if not fw_rev:
        return None
    prefixes = profile.supported_fw_prefixes
    if "" in prefixes:
        return None
    if any(fw_rev.startswith(prefix) for prefix in prefixes):
        return None
    return MotionErrorCode.E_UNSUPPORTED_PROFILE.value


def profile_limit_error(params: dict[str, Any], profile: DeviceProfile | None) -> str | None:
    if profile is None:
        return None
    # GW-R3-3: non-finite workspace axes defeat every outside-check comparison.
    for axis in ("x", "y", "z"):
        bound = profile.workspace_mm.get(axis) if isinstance(profile.workspace_mm, dict) else None
        if not isinstance(bound, (int, float)) or not math.isfinite(bound) or float(bound) <= 0:
            return MotionErrorCode.E_BAD_PARAMS.value
    path = params.get("path")
    if isinstance(path, list) and len(path) > profile.max_path_points:
        return MotionErrorCode.E_BAD_PARAMS.value
    feed = params.get("feed")
    if isinstance(feed, (int, float)) and float(feed) > profile.max_feed:
        return MotionErrorCode.E_BAD_PARAMS.value
    if isinstance(path, list):
        for point in path:
            if not isinstance(point, dict):
                return MotionErrorCode.E_BAD_PARAMS.value
            if _point_outside_workspace(point, profile):
                return MotionErrorCode.E_BAD_PARAMS.value
    return None


def _point_outside_workspace(point: dict[str, Any], profile: DeviceProfile) -> bool:
    for axis in ("x", "y", "z"):
        value = point.get(axis, 0)
        if not isinstance(value, (int, float)):
            return True
        # AUDIT-10-V1：NaN/Inf 绕过比较（IEEE 754），物理安全关键——必须拦截。
        if not math.isfinite(value):
            return True
        bound = profile.workspace_mm[axis]
        if not isinstance(bound, (int, float)) or not math.isfinite(bound):
            return True
        if float(value) < 0 or float(value) > float(bound):
            return True
    return False
