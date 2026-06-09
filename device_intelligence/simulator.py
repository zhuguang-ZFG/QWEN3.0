"""M4: Simulator — deterministic motion simulation metrics.

Computes draw distance, pen-up distance, estimated runtime, and risk score
from a TaskPlan's path. All calculations are pure geometry — no side effects.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from typing import Any

from .schemas import DeviceProfile, TaskPlan

DEFAULT_FEED = 600  # mm/min fallback when plan has no feed


@dataclass(frozen=True)
class SimResult:
    draw_distance_mm: float
    pen_up_distance_mm: float
    estimated_runtime_sec: float
    risk_score: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "draw_distance_mm": round(self.draw_distance_mm, 3),
            "pen_up_distance_mm": round(self.pen_up_distance_mm, 3),
            "estimated_runtime_sec": round(self.estimated_runtime_sec, 3),
            "risk_score": round(self.risk_score, 4),
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def simulate_motion(plan: TaskPlan, profile: DeviceProfile | None = None) -> SimResult:
    """Simulate a motion plan and return deterministic metrics.

    - draw_distance_mm:   sum of XY distances for pen-down segments (z == 0 at start)
    - pen_up_distance_mm:  sum of XY distances for pen-up segments (z > 0 at start)
    - estimated_runtime_sec: total_xy_distance / feed * 60
    - risk_score: 0.0–1.0 based on workspace usage and path complexity
    """
    path = plan.params.get("path")
    if not isinstance(path, list) or len(path) < 2:
        return SimResult(
            draw_distance_mm=0.0,
            pen_up_distance_mm=0.0,
            estimated_runtime_sec=0.0,
            risk_score=0.0,
            warnings=["no path to simulate"] if not path else [],
        )

    feed = float(plan.params.get("feed", DEFAULT_FEED))
    if feed <= 0:
        feed = float(DEFAULT_FEED)

    draw_dist = 0.0
    pen_up_dist = 0.0
    warnings: list[str] = []

    for i in range(len(path) - 1):
        a = path[i]
        b = path[i + 1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            warnings.append(f"invalid point at index {i}")
            continue

        xy_dist = _xy_distance(a, b)
        z_start = float(a.get("z", 0))

        if z_start > 0:
            pen_up_dist += xy_dist
        else:
            draw_dist += xy_dist

    total_dist = draw_dist + pen_up_dist
    runtime = total_dist / feed * 60.0 if feed > 0 else 0.0

    risk = _compute_risk(path, draw_dist, profile)

    return SimResult(
        draw_distance_mm=round(draw_dist, 3),
        pen_up_distance_mm=round(pen_up_dist, 3),
        estimated_runtime_sec=round(runtime, 3),
        risk_score=round(risk, 4),
        warnings=warnings,
    )


def _xy_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = float(b.get("x", 0)) - float(a.get("x", 0))
    dy = float(b.get("y", 0)) - float(a.get("y", 0))
    return math.sqrt(dx * dx + dy * dy)


def _compute_risk(
    path: list[Any],
    draw_distance: float,
    profile: DeviceProfile | None,
) -> float:
    """Risk score 0.0–1.0 from workspace usage ratio and path complexity."""
    if profile is None:
        # No profile → moderate baseline risk
        point_count = len(path)
        complexity = min(1.0, point_count / 200.0)
        return round(min(1.0, 0.1 + complexity * 0.3), 4)

    # Workspace usage: how much of the diagonal is consumed
    ws = profile.workspace_mm
    ws_diag = math.sqrt(ws["x"] ** 2 + ws["y"] ** 2)
    usage_ratio = draw_distance / ws_diag if ws_diag > 0 else 0.0

    # Point density risk
    point_count = len(path)
    max_points = profile.max_path_points
    density_ratio = min(1.0, point_count / max_points) if max_points > 0 else 0.0

    # Combined: 60% workspace usage + 40% density
    risk = min(1.0, usage_ratio * 0.6 + density_ratio * 0.4)
    return round(risk, 4)
