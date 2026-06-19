"""Device profile data models — capability, preferences, history, and profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from device_intelligence.schemas import DeviceProfile as DeviceIntelligenceProfile

# ── Constants ──────────────────────────────────────────────────────────────

COMPUTE_LEVELS = frozenset({"low", "medium", "high"})
PRIORITY_VALUES = frozenset({"speed", "quality", "balanced"})
COST_SENSITIVITY_VALUES = frozenset({"low", "medium", "high"})


# ── Helper: compute level ranking ──────────────────────────────────────────


def _compute_level_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 0)


# ── Data structures ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeviceCapability:
    """Hardware capability constraints for model/backend filtering."""

    compute_level: str = "low"  # low / medium / high
    memory_mb: int = 512
    supported_features: tuple[str, ...] = ("vector_path", "text")

    def __post_init__(self) -> None:
        if self.compute_level not in COMPUTE_LEVELS:
            raise ValueError(f"compute_level must be one of {sorted(COMPUTE_LEVELS)}, got {self.compute_level!r}")

    def is_compatible(self, model_requirement: dict[str, Any]) -> bool:
        """Check if this device can satisfy a model's requirement dict.

        Expected keys in *model_requirement*:
          min_compute_level — minimum compute level required
          min_memory_mb    — minimum memory required
          requires_features — set/list of features the model needs
        """
        if "min_compute_level" in model_requirement:
            required = model_requirement["min_compute_level"]
            if _compute_level_rank(self.compute_level) < _compute_level_rank(required):
                return False

        if "min_memory_mb" in model_requirement:
            if self.memory_mb < model_requirement["min_memory_mb"]:
                return False

        if "requires_features" in model_requirement:
            needed = set(model_requirement["requires_features"])
            if needed - set(self.supported_features):
                return False

        return True


@dataclass(frozen=True)
class DevicePreferences:
    """User/device preferences that adjust routing weights."""

    latency_sensitive: bool = True
    quality_priority: str = "speed"  # speed / quality / balanced
    cost_sensitivity: str = "low"  # low / medium / high

    def __post_init__(self) -> None:
        if self.quality_priority not in PRIORITY_VALUES:
            raise ValueError(
                f"quality_priority must be one of {sorted(PRIORITY_VALUES)}, got {self.quality_priority!r}"
            )
        if self.cost_sensitivity not in COST_SENSITIVITY_VALUES:
            raise ValueError(
                f"cost_sensitivity must be one of {sorted(COST_SENSITIVITY_VALUES)}, got {self.cost_sensitivity!r}"
            )


@dataclass(frozen=True)
class DeviceHistory:
    """Historical usage patterns inferred from routing artifacts."""

    preferred_models: tuple[str, ...] = ()
    failed_backends: tuple[str, ...] = ()
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    total_tasks: int = 0


@dataclass(frozen=True)
class DeviceProfile:
    """Full device profile combining capability, preferences, and history."""

    device_id: str
    capability: DeviceCapability = field(default_factory=DeviceCapability)
    preferences: DevicePreferences = field(default_factory=DevicePreferences)
    history: DeviceHistory = field(default_factory=DeviceHistory)
    profile_id: str = ""
    model: str = ""
    workspace_mm: dict[str, float] = field(default_factory=lambda: {"x": 100.0, "y": 100.0, "z": 20.0})
    max_feed: float = 1200.0
    max_path_points: int = 200
    capabilities: tuple[str, ...] = ("run_path", "home", "pause", "resume", "stop", "get_device_info")
    supported_fw_prefixes: tuple[str, ...] = ("",)
    profile_version: str = "1"
    fw_rev: str = ""
    u1_fw_rev: str = ""
    hw_rev: str = ""
    limits: dict[str, int] = field(default_factory=lambda: {"max_points": 200})

    def to_device_intelligence_profile(self) -> DeviceIntelligenceProfile:
        """Convert to DeviceIntelligence DeviceProfile for unified schema."""
        return DeviceIntelligenceProfile(
            profile_id=self.profile_id,
            model=self.model,
            workspace_mm=self.workspace_mm,
            max_feed=self.max_feed,
            max_path_points=self.max_path_points,
            capabilities=self.capabilities,
            supported_fw_prefixes=self.supported_fw_prefixes,
            profile_version=self.profile_version,
            fw_rev=self.fw_rev,
            u1_fw_rev=self.u1_fw_rev,
            hw_rev=self.hw_rev,
            limits=self.limits,
        )
