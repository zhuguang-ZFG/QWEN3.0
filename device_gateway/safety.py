"""Safety constraints for first-slice device motion tasks."""
from __future__ import annotations

from typing import Any

MAX_POINTS = 128
MAX_FEED = 1200
DEFAULT_FEED = 900
DEFAULT_WORKSPACE_MM = {"x": 100.0, "y": 100.0, "z": 20.0}


class SafetyError(ValueError):
    pass


def safe_point(x: float, y: float, z: float = 0.0) -> dict[str, float]:
    if not (0 <= x <= DEFAULT_WORKSPACE_MM["x"] and 0 <= y <= DEFAULT_WORKSPACE_MM["y"]):
        raise SafetyError("point outside workspace")
    if not (0 <= z <= DEFAULT_WORKSPACE_MM["z"]):
        raise SafetyError("z outside workspace")
    return {"x": round(float(x), 3), "y": round(float(y), 3), "z": round(float(z), 3)}


def validate_run_path_params(params: dict[str, Any]) -> dict[str, Any]:
    path = params.get("path")
    if not isinstance(path, list) or not path:
        raise SafetyError("path must be a non-empty list")
    if len(path) > MAX_POINTS:
        raise SafetyError("path has too many points")
    feed = params.get("feed", DEFAULT_FEED)
    if not isinstance(feed, (int, float)) or feed <= 0 or feed > MAX_FEED:
        raise SafetyError("feed is outside allowed range")
    normalized_path = []
    for point in path:
        if not isinstance(point, dict):
            raise SafetyError("path point must be an object")
        normalized_path.append(
            safe_point(
                float(point.get("x", 0.0)),
                float(point.get("y", 0.0)),
                float(point.get("z", 0.0)),
            )
        )
    result = dict(params)
    result["feed"] = int(feed)
    result["path"] = normalized_path
    return result

