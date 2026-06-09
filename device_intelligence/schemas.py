"""Deterministic device intelligence schemas."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Any

DEFAULT_WORKSPACE_MM = {"x": 100.0, "y": 100.0, "z": 20.0}


@dataclass(frozen=True)
class DeviceProfile:
    profile_id: str
    model: str
    workspace_mm: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WORKSPACE_MM))
    max_feed: float = 1200.0
    max_path_points: int = 200
    capabilities: tuple[str, ...] = ("run_path", "home", "pause", "resume", "stop", "get_device_info")
    supported_fw_prefixes: tuple[str, ...] = ("",)
    profile_version: str = "1"

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id is required")
        if not self.model:
            raise ValueError("model is required")
        workspace = _normalize_workspace(self.workspace_mm)
        if self.max_feed <= 0:
            raise ValueError("max_feed must be positive")
        if self.max_path_points < 1:
            raise ValueError("max_path_points must be positive")
        object.__setattr__(self, "workspace_mm", workspace)
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities))))
        object.__setattr__(self, "supported_fw_prefixes", tuple(self.supported_fw_prefixes or ("",)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "model": self.model,
            "workspace_mm": deepcopy(self.workspace_mm),
            "max_feed": float(self.max_feed),
            "max_path_points": int(self.max_path_points),
            "capabilities": list(self.capabilities),
            "supported_fw_prefixes": list(self.supported_fw_prefixes),
            "profile_version": self.profile_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class TaskPlan:
    plan_id: str
    device_id: str
    capability: str
    params: dict[str, Any]
    profile_id: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not self.device_id:
            raise ValueError("device_id is required")
        if not self.capability:
            raise ValueError("capability is required")
        object.__setattr__(self, "params", deepcopy(dict(self.params)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "device_id": self.device_id,
            "params": deepcopy(self.params),
            "plan_id": self.plan_id,
            "profile_id": self.profile_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_workspace(workspace_mm: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        value = float(workspace_mm.get(axis, DEFAULT_WORKSPACE_MM[axis]))
        if value <= 0:
            raise ValueError(f"workspace_mm.{axis} must be positive")
        normalized[axis] = value
    return normalized
