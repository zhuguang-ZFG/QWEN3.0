"""Tests for observability/prometheus_metrics.py startup instruments."""

from __future__ import annotations

import pytest

from observability import prometheus_metrics


@pytest.fixture(autouse=True)
def _reset_prometheus_state(monkeypatch):
    """Enable metrics and reset the global registry before each test."""
    monkeypatch.setenv("LIMA_PROMETHEUS_METRICS", "1")
    monkeypatch.setattr(prometheus_metrics, "_registry", None)
    monkeypatch.setattr(prometheus_metrics, "_counters", {})
    monkeypatch.setattr(prometheus_metrics, "_histograms", {})
    monkeypatch.setattr(prometheus_metrics, "_gauges", {})


def _metric_output() -> str:
    return prometheus_metrics.generate_metrics().decode("utf-8")


def test_record_startup_phase_emits_histogram():
    prometheus_metrics.record_startup_phase("health_state.load", 42.0)
    output = _metric_output()
    assert 'lima_startup_phase_duration_ms_bucket{le="50.0",phase="health_state.load"} 1.0' in output
    assert 'lima_startup_phase_duration_ms_count{phase="health_state.load"} 1.0' in output
    assert 'lima_startup_phase_duration_ms_sum{phase="health_state.load"} 42.0' in output


def test_record_startup_phase_disabled_when_metrics_off(monkeypatch):
    monkeypatch.setenv("LIMA_PROMETHEUS_METRICS", "0")
    prometheus_metrics.record_startup_phase("probe_loop.start", 100.0)
    assert prometheus_metrics.generate_metrics() == b""


def test_record_startup_status_sets_gauge():
    prometheus_metrics.record_startup_status("ready")
    output = _metric_output()
    assert "lima_startup_status 1.0" in output

    prometheus_metrics.record_startup_status("warming")
    output = _metric_output()
    assert "lima_startup_status 0.5" in output

    prometheus_metrics.record_startup_status("starting")
    output = _metric_output()
    assert "lima_startup_status 0.0" in output


def test_record_startup_status_unknown_defaults_to_zero():
    prometheus_metrics.record_startup_status("unexpected")
    output = _metric_output()
    assert "lima_startup_status 0.0" in output


def test_record_startup_phase_does_not_raise_when_instruments_unavailable(monkeypatch):
    monkeypatch.setattr(
        prometheus_metrics, "_ensure_instruments", lambda: (_ for _ in ()).throw(RuntimeError("no client"))
    )
    prometheus_metrics.record_startup_phase("test", 1.0)


def test_record_startup_status_does_not_raise_when_instruments_unavailable(monkeypatch):
    monkeypatch.setattr(
        prometheus_metrics, "_ensure_instruments", lambda: (_ for _ in ()).throw(RuntimeError("no client"))
    )
    prometheus_metrics.record_startup_status("ready")


def test_record_image_cache_lookup_emits_counter():
    prometheus_metrics.record_image_cache_lookup("hit")
    prometheus_metrics.record_image_cache_lookup("miss")
    output = _metric_output()
    assert 'lima_image_cache_lookups_total{result="hit"} 1.0' in output
    assert 'lima_image_cache_lookups_total{result="miss"} 1.0' in output


def test_record_image_request_emits_counter():
    prometheus_metrics.record_image_request("xmiaom_gpt_image_2")
    prometheus_metrics.record_image_request("pollinations")
    output = _metric_output()
    assert 'lima_image_requests_total{backend="xmiaom_gpt_image_2"} 1.0' in output
    assert 'lima_image_requests_total{backend="pollinations"} 1.0' in output


def test_record_image_cache_entries_sets_gauge():
    prometheus_metrics.record_image_cache_entries(42)
    output = _metric_output()
    assert "lima_image_cache_entries 42.0" in output
