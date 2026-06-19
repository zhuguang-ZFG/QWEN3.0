"""Sources for building DeviceProfile instances."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from device_gateway.device_profile._artifact_parser import _MAX_EVIDENCE_AGE_S, _parse_evidence_log
from device_gateway.device_profile.models import DeviceCapability, DeviceHistory, DevicePreferences, DeviceProfile

_log = logging.getLogger(__name__)


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
    """Infer a DeviceProfile from historical route evidence artifacts."""
    log_path = Path(artifact_dir) / f"route_evidence_{device_id}.log"
    if not log_path.exists():
        return None
    try:
        models_seen, backends_failed, latencies, successes, total = _parse_evidence_log(log_path, max_age_s)
    except OSError as e:
        _log.warning("Failed to read artifact log for %s: %s", device_id, e)
        return None
    if total == 0:
        return None
    preferred = tuple(sorted(models_seen, key=models_seen.__getitem__, reverse=True))
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
