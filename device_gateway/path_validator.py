"""Device Gateway path validator — validates motion run_path parameters.

Catches bad input at task-creation time (Server side) so invalid tasks
never reach the device. Returns structured error codes matching the
MotionErrorCode enum in protocol_families.py.
"""
from __future__ import annotations

from device_gateway.protocol_families import MotionErrorCode

MAX_PATH_POINTS = 200
MAX_POINT_COORD = 500.0
MIN_POINT_COORD = -500.0
MAX_FEED = 2000.0
MIN_FEED = 1.0

CAPABILITY_PATH_MAP: dict[str, frozenset[str]] = {
    "run_path": frozenset({"path", "feed"}),
    "write_text": frozenset({"path", "feed", "text"}),
    "draw_generated": frozenset({"path", "feed", "prompt"}),
    "home": frozenset(),
    "pause": frozenset(),
    "resume": frozenset(),
    "stop": frozenset(),
    "get_device_info": frozenset(),
}

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "get_device_info"})


def validate_run_path_params(params: dict) -> tuple[dict, str | None]:
    """Validate motion task run_path parameters.

    Returns (sanitized_params, None) on success or ({}, error_code) on failure.
    The error_code is a MotionErrorCode string value ready for the failure event.
    """
    if not isinstance(params, dict):
        return {}, MotionErrorCode.E_BAD_PARAMS.value

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
            if val < MIN_POINT_COORD or val > MAX_POINT_COORD:
                return {}, MotionErrorCode.E_BAD_PARAMS.value

    feed = float(params.get("feed", 500.0))
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

    sanitized, error = validate_run_path_params(params)
    if error:
        return {}, error

    for field in required:
        if field in ("path", "feed"):
            continue  # validated by validate_run_path_params
        if field not in params or not params[field]:
            return {}, MotionErrorCode.E_BAD_PARAMS.value

    for key, value in params.items():
        if isinstance(value, str):
            limit = 4096 if key == "preview_svg" else 120
            sanitized[key] = value[:limit]
        elif isinstance(value, (int, float)):
            sanitized[key] = value

    return sanitized, None
