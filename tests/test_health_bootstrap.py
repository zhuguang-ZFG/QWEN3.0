"""Tests for startup health/circuit-breaker registration."""

from __future__ import annotations

import health_state
import health_tracker
import router_circuit_breaker
from health_bootstrap import bootstrap_runtime_health


def setup_function():
    health_state.reset_all_state()
    router_circuit_breaker.reset_for_tests()


def test_seed_backends_registers_unknown_state():
    seeded = health_tracker.seed_backends(["alpha", "beta"])
    assert seeded == 2
    hmap = health_tracker.get_health_map()
    assert hmap["alpha"] == "unknown"
    assert hmap["beta"] == "unknown"
    assert health_tracker.get_backend_state("alpha")["state"] == "ok"


def test_circuit_breaker_seed_pre_registers_slots():
    n = router_circuit_breaker.seed_backends(["alpha", "beta"])
    assert n == 2
    status = router_circuit_breaker.cb_status()
    assert set(status.keys()) == {"alpha", "beta"}
    assert status["alpha"]["state"] == "closed"


def test_bootstrap_runtime_health_uses_registry(monkeypatch):
    monkeypatch.setattr(
        "backends_registry.BACKENDS",
        {"x": {}, "y": {}},
        raising=False,
    )
    result = bootstrap_runtime_health()
    assert result["backends"] == 2
    assert result["health_seeded"] == 2
    assert result["cb_seeded"] == 2
