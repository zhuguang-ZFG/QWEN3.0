"""Tests that lifespan state changes emit Prometheus startup metrics."""

from __future__ import annotations

import pytest

import server_lifespan_state as state


@pytest.fixture(autouse=True)
def _reset_state():
    state.reset_startup_state()
    state.STARTUP_PHASES.clear()


def test_record_phase_emits_prometheus_metric(monkeypatch):
    recorded: list[tuple[str, float]] = []
    monkeypatch.setattr(
        "observability.prometheus_metrics.record_startup_phase",
        lambda phase, elapsed_ms: recorded.append((phase, elapsed_ms)),
    )

    state.record_phase("health_state.load", 12.3)
    assert recorded == [("health_state.load", 12.3)]


def test_record_phase_swallows_prometheus_import_error(monkeypatch):
    def _broken_import(*_args, **_kwargs):
        raise ImportError("no metrics")

    monkeypatch.setattr(
        "observability.prometheus_metrics.record_startup_phase",
        _broken_import,
    )
    phase = state.record_phase("health_state.load", 12.3)
    assert phase["name"] == "health_state.load"


def test_set_startup_status_emits_prometheus_metric(monkeypatch):
    recorded: list[str] = []
    monkeypatch.setattr(
        "observability.prometheus_metrics.record_startup_status",
        lambda status: recorded.append(status),
    )

    state.set_startup_status("warming")
    assert recorded == ["warming"]


def test_set_startup_status_swallows_prometheus_import_error(monkeypatch):
    def _broken_import(*_args, **_kwargs):
        raise ImportError("no metrics")

    monkeypatch.setattr(
        "observability.prometheus_metrics.record_startup_status",
        _broken_import,
    )
    state.set_startup_status("ready")
    assert state.get_startup_state()["status"] == "ready"
