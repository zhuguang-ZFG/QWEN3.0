"""Device profile routing inputs — hardware capability, preferences, and history.

Device profiles provide first-class routing signals that influence model and
backend selection.  Profiles come from two sources:

1. **Hello frame** — device reports its capabilities and preferences at connect.
2. **Route evidence inference** — historical routing artifacts (from
   artifact_recorder) are aggregated to build a history profile.

A profile includes capability constraints (compute level, memory, supported
features), preference hints (latency vs cost vs quality), and historical
telemetry (preferred models, failed backends, success rates).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ── Storage for device profiles ──────────────────────────────────────────

_device_profiles: dict[str, DeviceProfile] = {}

# ── Constants ──────────────────────────────────────────────────────────────

COMPUTE_LEVELS = frozenset({"low", "medium", "high"})
PRIORITY_VALUES = frozenset({"speed", "quality", "balanced"})
COST_SENSITIVITY_VALUES = frozenset({"low", "medium", "high"})

# Maximum evidence age for history inference (seconds = 7 days)
_MAX_EVIDENCE_AGE_S = 7 * 24 * 3600

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
            raise ValueError(f"quality_priority must be one of {sorted(PRIORITY_VALUES)}, got {self.quality_priority!r}")
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


# ── Public API ─────────────────────────────────────────────────────────────


def register_device_profile(profile: DeviceProfile) -> None:
    """Register a device profile so it's available for routing decisions."""
    _device_profiles[profile.device_id] = profile


def get_device_profile(device_id: str) -> DeviceProfile | None:
    """Look up a registered device profile by device_id."""
    return _device_profiles.get(device_id)


def profile_from_hello_frame(
    device_id: str,
    hello: dict[str, Any],
) -> DeviceProfile:
    """Build a DeviceProfile from a device hello/connect frame.

    Expected hello frame keys:
      compute_level        — "low" / "medium" / "high" (default "low")
      memory_mb            — int (default 512)
      supported_features   — list[str] (default ["vector_path", "text"])
      latency_sensitive    — bool (default True)
      quality_priority     — "speed" / "quality" / "balanced" (default "speed")
      cost_sensitivity     — "low" / "medium" / "high" (default "low")
    """
    caps = hello.get("capability", hello)
    cap = DeviceCapability(
        compute_level=str(caps.get("compute_level", "low")),
        memory_mb=int(caps.get("memory_mb", 512)),
        supported_features=tuple(caps.get("supported_features", ("vector_path", "text"))),
    )

    prefs_data = hello.get("preferences", hello)
    prefs = DevicePreferences(
        latency_sensitive=bool(prefs_data.get("latency_sensitive", True)),
        quality_priority=str(prefs_data.get("quality_priority", "speed")),
        cost_sensitivity=str(prefs_data.get("cost_sensitivity", "low")),
    )

    hist_data = hello.get("history", {})

    def _safe_tuple(key: str) -> tuple[str, ...]:
        raw = hist_data.get(key, ())
        return tuple(raw) if isinstance(raw, (list, tuple)) else ()

    hist = DeviceHistory(
        preferred_models=_safe_tuple("preferred_models"),
        failed_backends=_safe_tuple("failed_backends"),
        avg_latency_ms=float(hist_data.get("avg_latency_ms", 0.0)),
        success_rate=float(hist_data.get("success_rate", 0.0)),
        total_tasks=int(hist_data.get("total_tasks", 0)),
    )

    return DeviceProfile(device_id=device_id, capability=cap, preferences=prefs, history=hist)


def infer_profile_from_artifacts(
    device_id: str,
    artifact_dir: str | Path = "device_artifacts",
    max_age_s: float = _MAX_EVIDENCE_AGE_S,
) -> DeviceProfile | None:
    """Infer a DeviceProfile from historical route evidence artifacts.

    Reads ``route_evidence_{device_id}.log`` (JSONL) and aggregates
    preferred_models and failed_backends.
    """
    log_path = Path(artifact_dir) / f"route_evidence_{device_id}.log"
    if not log_path.exists():
        return None

    models_seen: dict[str, int] = {}
    backends_failed: set[str] = set()
    latencies: list[float] = []
    successes = 0
    total = 0

    try:
        for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Age filter
            ts = rec.get("timestamp", "")
            age = _age_seconds(ts)
            if age is not None and age > max_age_s:
                continue

            total += 1

            model = rec.get("selected_model", "")
            if model:
                models_seen[model] = models_seen.get(model, 0) + 1

            backend = rec.get("backend", "")
            reason = rec.get("reason", "")
            if backend and ("fail" in reason.lower() or "error" in reason.lower()):
                backends_failed.add(backend)

            # Heuristic: success if route_policy non-empty
            rp = rec.get("route_policy", {})
            if isinstance(rp, dict) and rp:
                successes += 1

    except OSError as e:
        _log.warning("Failed to read artifact log for %s: %s", device_id, e)
        return None

    if total == 0:
        return None

    # Sort models by frequency (descending)
    preferred = tuple(sorted(models_seen, key=models_seen.__getitem__, reverse=True))

    # Cap total tasks to what we actually counted
    hist = DeviceHistory(
        preferred_models=preferred,
        failed_backends=tuple(sorted(backends_failed)),
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        success_rate=successes / total if total else 0.0,
        total_tasks=total,
    )

    return DeviceProfile(
        device_id=device_id,
        capability=DeviceCapability(),
        preferences=DevicePreferences(),
        history=hist,
    )


# ── Helper: compute level ranking ──────────────────────────────────────────


def _compute_level_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 0)


def _age_seconds(timestamp: str) -> float | None:
    """Compute age in seconds of an ISO-8601 timestamp.  Returns None on parse failure."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except (ValueError, TypeError):
        return None


# ── Serialisation helpers ──────────────────────────────────────────────────


def profile_to_dict(p: DeviceProfile) -> dict[str, Any]:
    """Convert a DeviceProfile to a JSON-serialisable dict."""
    return {
        "device_id": p.device_id,
        "capability": {
            "compute_level": p.capability.compute_level,
            "memory_mb": p.capability.memory_mb,
            "supported_features": list(p.capability.supported_features),
        },
        "preferences": {
            "latency_sensitive": p.preferences.latency_sensitive,
            "quality_priority": p.preferences.quality_priority,
            "cost_sensitivity": p.preferences.cost_sensitivity,
        },
        "history": {
            "preferred_models": list(p.history.preferred_models),
            "failed_backends": list(p.history.failed_backends),
            "avg_latency_ms": p.history.avg_latency_ms,
            "success_rate": p.history.success_rate,
            "total_tasks": p.history.total_tasks,
        },
    }


def profile_from_dict(data: dict[str, Any]) -> DeviceProfile:
    """Rebuild a DeviceProfile from a dict (inverse of *profile_to_dict*)."""
    cap_data = data.get("capability", {})
    prefs_data = data.get("preferences", {})
    hist_data = data.get("history", {})

    cap = DeviceCapability(
        compute_level=str(cap_data.get("compute_level", "low")),
        memory_mb=int(cap_data.get("memory_mb", 512)),
        supported_features=tuple(cap_data.get("supported_features", ("vector_path", "text"))),
    )
    prefs = DevicePreferences(
        latency_sensitive=bool(prefs_data.get("latency_sensitive", True)),
        quality_priority=str(prefs_data.get("quality_priority", "speed")),
        cost_sensitivity=str(prefs_data.get("cost_sensitivity", "low")),
    )
    hist = DeviceHistory(
        preferred_models=tuple(hist_data.get("preferred_models", ())),
        failed_backends=tuple(hist_data.get("failed_backends", ())),
        avg_latency_ms=float(hist_data.get("avg_latency_ms", 0.0)),
        success_rate=float(hist_data.get("success_rate", 0.0)),
        total_tasks=int(hist_data.get("total_tasks", 0)),
    )
    return DeviceProfile(
        device_id=str(data.get("device_id", "unknown")),
        capability=cap,
        preferences=prefs,
        history=hist,
    )


# ── Module reset (for tests) ──────────────────────────────────────────────


def reset_device_profiles_for_tests() -> None:
    """Clear all registered profiles (test isolation hook)."""
    _device_profiles.clear()
