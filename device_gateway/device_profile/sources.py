"""Sources for building DeviceProfile instances."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from device_gateway.device_profile._artifact_parser import _MAX_EVIDENCE_AGE_S, _parse_evidence_log
from device_gateway.device_profile.models import DeviceCapability, DeviceHistory, DevicePreferences, DeviceProfile

_log = logging.getLogger(__name__)


def _workspace_from_hello(hello: dict[str, Any]) -> dict[str, float]:
    """Prefer complete hello.workspace_mm (x/y/z all present + valid); else product canvas."""
    from device_gateway.path_workspace import workspace_axes_ok
    from device_gateway.profiles import PRODUCT_WRITING_WORKSPACE_MM

    raw = hello.get("workspace_mm")
    if isinstance(raw, dict) and all(k in raw for k in ("x", "y", "z")):
        try:
            ws = {"x": float(raw["x"]), "y": float(raw["y"]), "z": float(raw["z"])}
            if workspace_axes_ok(ws):
                return ws
        except (TypeError, ValueError):
            pass
    return {
        "x": float(PRODUCT_WRITING_WORKSPACE_MM["x"]),
        "y": float(PRODUCT_WRITING_WORKSPACE_MM["y"]),
        "z": float(PRODUCT_WRITING_WORKSPACE_MM["z"]),
    }


def _capability_prefs_history(hello: dict[str, Any]) -> tuple[DeviceCapability, DevicePreferences, DeviceHistory]:
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
    hist_data = hello.get("history", {}) if isinstance(hello.get("history"), dict) else {}

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
    return cap, prefs, hist


def _limits_from_hello(hello: dict[str, Any]) -> tuple[float, int, tuple[str, ...]]:
    caps_list = hello.get("capabilities")
    if isinstance(caps_list, (list, tuple)) and caps_list:
        capabilities = tuple(str(c) for c in caps_list)
    else:
        capabilities = (
            "run_path",
            "home",
            "pause",
            "resume",
            "stop",
            "get_device_info",
            "write_text",
            "draw_generated",
        )
    try:
        max_path_points = int(hello.get("max_path_points", 200))
        if max_path_points <= 0:
            max_path_points = 200
    except (TypeError, ValueError):
        max_path_points = 200
    try:
        max_feed = float(hello.get("max_feed", 2000.0))
        if max_feed <= 0:
            max_feed = 2000.0
    except (TypeError, ValueError):
        max_feed = 2000.0
    return max_feed, max_path_points, capabilities


def profile_from_hello_frame(device_id: str, hello: dict[str, Any]) -> DeviceProfile:
    """Build a DeviceProfile from hello so register_device_profile can complete path gen."""
    cap, prefs, hist = _capability_prefs_history(hello)
    max_feed, max_path_points, capabilities = _limits_from_hello(hello)
    profile_id = str(hello.get("profile_id") or f"hello-{device_id}").strip() or f"hello-{device_id}"
    fw_rev = str(hello.get("fw_rev") or hello.get("firmwareVersion") or "")
    return DeviceProfile(
        device_id=device_id,
        capability=cap,
        preferences=prefs,
        history=hist,
        profile_id=profile_id[:80],
        model=str(hello.get("model") or "esp32_writing_machine"),
        workspace_mm=_workspace_from_hello(hello),
        max_feed=max_feed,
        max_path_points=max_path_points,
        capabilities=capabilities,
        supported_fw_prefixes=("",),
        profile_version="1",
        fw_rev=fw_rev,
        hw_rev=str(hello.get("hw_rev") or ""),
        limits={"max_points": max_path_points},
    )


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
