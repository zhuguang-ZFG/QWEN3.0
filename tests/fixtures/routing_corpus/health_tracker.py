"""Fixture stub: cooldown and health scoring tracker."""

import time

_cooldown_until: dict[str, float] = {}
_health_map: dict[str, str] = {}


def is_cooled_down(backend: str) -> bool:
    deadline = _cooldown_until.get(backend, 0)
    return time.monotonic() < deadline


def record_failure(backend: str, error_code: int | None = None, error_text: str = ""):
    _health_map[backend] = "degraded"
    _cooldown_until[backend] = time.monotonic() + 30


def record_success(backend: str, latency_ms: float):
    _health_map[backend] = "healthy"
    _cooldown_until.pop(backend, None)


def get_scores() -> dict[str, float]:
    return {name: 80.0 if status == "healthy" else 20.0 for name, status in _health_map.items()}
