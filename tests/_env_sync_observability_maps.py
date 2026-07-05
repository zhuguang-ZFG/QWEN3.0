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
        "LIMA_SERVICE_NAME": (settings.OBSERVABILITY, "service_name", lambda v: v or "lima-router"),
    }
