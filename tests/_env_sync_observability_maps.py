"""Observability env-to-singleton mappings for the test monkeypatch wrapper."""

from __future__ import annotations

from typing import Any, Callable

from tests._env_sync_maps import _bool_env


def _observability_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_TELEMETRY_JSONL_MAX_BYTES": (
            settings.OBSERVABILITY,
            "telemetry_jsonl_max_bytes",
            lambda v: int(v or str(1024 * 1024)),
        ),
        "OPENOBSERVE_ENABLED": (settings.OBSERVABILITY, "openobserve_enabled", _bool_env),
        "LIMA_PROMETHEUS_METRICS": (settings.OBSERVABILITY, "prometheus_metrics", _bool_env),
        "LIMA_STRUCTURED_LOGGING": (settings.OBSERVABILITY, "structured_logging", _bool_env),
        "LIMA_SERVICE_NAME": (settings.OBSERVABILITY, "service_name", lambda v: v or "lima-router"),
        "LIMA_ROUTING_GUARD_ENABLED": (settings.OBSERVABILITY, "routing_guard_enabled", _bool_env),
        "LIMA_ROUTING_GUARD_WINDOW_SEC": (
            settings.OBSERVABILITY,
            "routing_guard_window_sec",
            lambda v: int(v or "600"),
        ),
        "LIMA_ROUTING_GUARD_QUARANTINE_SEC": (
            settings.OBSERVABILITY,
            "routing_guard_quarantine_sec",
            lambda v: int(v or "180"),
        ),
        "LIMA_ROUTING_GUARD_FAILURE_THRESHOLD": (
            settings.OBSERVABILITY,
            "routing_guard_failure_threshold",
            lambda v: int(v or "3"),
        ),
    }
