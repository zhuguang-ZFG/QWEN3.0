"""Device Gateway path validator — validates motion run_path parameters.

Catches bad input at task-creation time (Server side) so invalid tasks
never reach the device. Returns structured error codes matching the
MotionErrorCode enum in protocol_families.py.
"""

from __future__ import annotations

import math

from device_gateway.model_routing import CONTROL_CAPABILITIES
from device_gateway.protocol_families import MotionErrorCode
from device_intelligence.safety import profile_limit_error
from device_intelligence.schemas import DeviceProfile

MAX_PATH_POINTS = 200
MAX_POINT_COORD = 500.0
MIN_POINT_COORD = -500.0
MAX_FEED = 2000.0
MIN_FEED = 1.0

CAPABILITY_PATH_MAP: dict[str, frozenset[str]] = {
    "run_path": frozenset({"path", "feed"}),
    "write_text": frozenset({"path", "feed", "text"}),
    "draw_generated": frozenset({"path", "feed", "prompt"}),
    "handwriting": frozenset({"path", "feed", "text"}),
    "home": frozenset(),
    "pause": frozenset(),
    "resume": frozenset(),
    "stop": frozenset(),
    "estop": frozenset(),
    "get_device_info": frozenset(),
}

# Valid route_policy values per Edge-C schema
VALID_ROUTE_ROLES = frozenset({"device_control", "device_write", "device_draw", "device_vector", "device_unknown"})
VALID_PRIMARY_STRATEGIES = frozenset(
    {"deterministic", "image_then_vector", "svg_vector", "provided_path", "planner_required"}
)
VALID_ARTIFACT_REQUIRED = frozenset({"none", "preview_svg", "vector_path"})


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

    for point in path:
        if not isinstance(point, dict):
            return {}, MotionErrorCode.E_BAD_PARAMS.value
        for axis in ("x", "y", "z"):
            val = point.get(axis, 0)
            if not isinstance(val, (int, float)):
                return {}, MotionErrorCode.E_BAD_PARAMS.value
            # AUDIT-10-V1：NaN/Inf 绕过边界校验（IEEE 754 NaN 比较全 False）。
            # NaN 坐标下发物理机械臂会导致 G-code 未定义行为，可能撞机。
            if not math.isfinite(val):
                return {}, MotionErrorCode.E_BAD_PARAMS.value
            if val < MIN_POINT_COORD or val > MAX_POINT_COORD:
                return {}, MotionErrorCode.E_BAD_PARAMS.value

    # AUDIT-10-V2：feed 转换加 try/except，非数字返回结构化错误而非抛异常。
    try:
        feed = float(params.get("feed", 500.0))
    except (TypeError, ValueError):
        return {}, MotionErrorCode.E_BAD_PARAMS.value
    if feed < MIN_FEED or feed > MAX_FEED:
        return {}, MotionErrorCode.E_BAD_PARAMS.value

    return {
        "path": path,
        "feed": feed,
        "source_capability": str(params.get("source_capability", "unknown")),
    }, None


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

    sanitized, error = validate_run_path_params(params, profile=profile)
    if error:
        return {}, error

    for field in required:
        if field in ("path", "feed"):
            continue  # validated by validate_run_path_params
        if field not in params or not params[field]:
            return {}, MotionErrorCode.E_BAD_PARAMS.value

    for key, value in params.items():
        if isinstance(value, str):
            limit = 8192 if key == "preview_svg" else 120
            sanitized[key] = value[:limit]
        elif isinstance(value, (int, float)):
            sanitized[key] = value

    return sanitized, None


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
