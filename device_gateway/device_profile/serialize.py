"""Serialization helpers for DeviceProfile."""

from __future__ import annotations

from typing import Any

from device_gateway.device_profile.models import DeviceCapability, DeviceHistory, DevicePreferences, DeviceProfile


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
