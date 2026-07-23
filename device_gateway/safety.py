"""Device-gateway internal safety primitives (raise-style).

NOTE — this is NOT the production dispatch validator. Production task
dispatch validates motion params via ``device_gateway.path_validator.
validate_capability_params``, which returns a ``(sanitized, error)`` tuple using
the structured ``MotionErrorCode`` enum (``E_BAD_PARAMS`` …) ready for motion
events. The ``validate_run_path_params`` / ``safe_point`` here raise
``SafetyError(str)`` and are used only by gateway internals and tests.

If you need to reject a task at dispatch time, use ``path_validator`` — do not
route the raise-style functions below into the dispatch path (they would lose
the structured error code clients depend on).
"""

from __future__ import annotations

import math
from typing import Any

# Single source of truth with path_data / path_validator (was 128 vs 200 split).
from device_gateway.path_data import MAX_PATH_POINTS

# Product writing-machine canvas (U8, 300x300x80) — single source of truth lives
# in device_intelligence.schemas; import instead of duplicating. Unknown devices
# without a profile use this for path generation; incomplete routing still uses
# CONSERVATIVE_WORKSPACE_MM in profiles.py (60mm) for policy hints only.
from device_intelligence.schemas import DEFAULT_WORKSPACE_MM

MAX_POINTS = MAX_PATH_POINTS
MAX_FEED = 1200
DEFAULT_FEED = 900


class SafetyError(ValueError):
    pass


def safe_point(
    x: float,
    y: float,
    z: float = 0.0,
    *,
    workspace_mm: dict[str, float] | None = None,
) -> dict[str, float]:
    ws = workspace_mm or DEFAULT_WORKSPACE_MM
    max_x = float(ws.get("x", DEFAULT_WORKSPACE_MM["x"]))
    max_y = float(ws.get("y", DEFAULT_WORKSPACE_MM["y"]))
    max_z = float(ws.get("z", DEFAULT_WORKSPACE_MM["z"]))
    if not (0 <= x <= max_x and 0 <= y <= max_y):
        raise SafetyError("point outside workspace")
    if not (0 <= z <= max_z):
        raise SafetyError("z outside workspace")
    return {"x": round(float(x), 3), "y": round(float(y), 3), "z": round(float(z), 3)}


def validate_run_path_params(
    params: dict[str, Any],
    *,
    workspace_mm: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Raise-style validator (see module docstring). Dispatch uses path_validator."""
    path = params.get("path")
    if not isinstance(path, list) or not path:
        raise SafetyError("path must be a non-empty list")
    if len(path) > MAX_POINTS:
        raise SafetyError("path has too many points")
    feed = params.get("feed", DEFAULT_FEED)
    if not isinstance(feed, (int, float)) or not math.isfinite(feed) or feed <= 0 or feed > MAX_FEED:
        raise SafetyError("feed is outside allowed range")
    ws = workspace_mm or DEFAULT_WORKSPACE_MM
    normalized_path = []
    for point in path:
        if not isinstance(point, dict):
            raise SafetyError("path point must be an object")
        normalized_path.append(
            safe_point(
                float(point.get("x", 0.0)),
                float(point.get("y", 0.0)),
                float(point.get("z", 0.0)),
                workspace_mm=ws,
            )
        )
    result = dict(params)
    result["feed"] = int(feed)
    result["path"] = normalized_path
    return result
