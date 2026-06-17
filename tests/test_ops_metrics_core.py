"""Ops metrics core and Prometheus tests."""

import builtins
import importlib
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import server
from routes.ops_metrics import router

from ops_metrics_helpers import reload_prometheus_metrics


def test_ops_metrics_reads_starlette_app_state(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.state.stats = {
        "total_requests": 3,
        "backend_calls": {"backend-a": 2, "backend-b": 1},
        "start_time": 1,
    }
    app.include_router(router)

    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] == 3
    assert data["backend_calls"] == {"backend-a": 2, "backend-b": 1}
    assert "device_gateway" in data
    assert "agent_workers" in data


def test_server_exposes_stats_to_ops_metrics_router():
    assert server.app.state.stats is server._stats


def test_ops_metrics_accepts_production_backend_call_shape(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.state.stats = {
        "total_requests": 8,
        "backend_calls": {
            "backend-a": {"count": 5, "success": 4, "total_ms": 1200},
            "backend-b": {"count": 3, "success": 3, "total_ms": 90},
        },
        "start_time": 1,
    }
    app.include_router(router)

    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["backend_calls"] == {"backend-a": 5, "backend-b": 3}
    assert data["backend_call_details"]["backend-a"]["success"] == 4
    assert data["backend_call_details"]["backend-a"]["total_ms"] == 1200


def test_prometheus_metrics_disabled_returns_404(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.delenv("LIMA_PROMETHEUS_METRICS", raising=False)
    reload_prometheus_metrics()

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics/prometheus",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Prometheus metrics disabled"


def test_prometheus_metrics_records_request_when_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_PROMETHEUS_METRICS", "1")
    metrics = reload_prometheus_metrics()

    metrics.record_request("unit_backend", "success", 123.0)
    text = metrics.generate_metrics().decode("utf-8")

    assert "lima_requests_total" in text
    assert 'backend="unit_backend"' in text
    assert 'status="success"' in text


def test_prometheus_endpoint_returns_metrics_when_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_PROMETHEUS_METRICS", "1")
    metrics = reload_prometheus_metrics()
    metrics.record_request("endpoint_backend", "success", 88.0)

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics/prometheus",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'backend="endpoint_backend"' in response.text


def test_prometheus_metrics_enabled_dependency_missing_is_explicit(monkeypatch):
    monkeypatch.setenv("LIMA_PROMETHEUS_METRICS", "1")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "prometheus_client" or name.startswith("prometheus_client."):
            raise ImportError("blocked in test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    metrics = reload_prometheus_metrics()

    with pytest.raises(RuntimeError, match="prometheus_client"):
        metrics.validate_startup()


def test_prometheus_endpoint_returns_503_when_enabled_metrics_are_broken(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    import observability.prometheus_metrics as prometheus_metrics

    monkeypatch.setattr(prometheus_metrics, "is_enabled", lambda: True)
    monkeypatch.setattr(
        prometheus_metrics,
        "generate_metrics",
        lambda: (_ for _ in ()).throw(RuntimeError("prometheus_client missing")),
    )

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics/prometheus",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 503
    assert response.json()["error"] == "Prometheus metrics unavailable"


def test_request_tracking_records_prometheus_request(monkeypatch):
    from routes import request_tracking
    import observability.prometheus_metrics as prometheus_metrics

    calls = []
    request_tracking.inject_state(
        {
            "total_requests": 0,
            "backend_calls": {},
            "intent_distribution": {},
            "recent_logs": [],
        },
        threading.Lock(),
    )
    monkeypatch.setattr(
        prometheus_metrics,
        "record_request",
        lambda backend, status, duration_ms: calls.append((backend, status, duration_ms)),
    )

    request_tracking.record_request(
        "query",
        "backend-a",
        "coding",
        42,
        success=False,
    )

    assert calls == [("backend-a", "error", 42.0)]


def test_prometheus_exporter_lifecycle_is_default_off_and_idempotent(monkeypatch):
    import observability.prometheus_metrics as prometheus_metrics
    import observability.prometheus_exporter as prometheus_exporter

    prometheus_exporter = importlib.reload(prometheus_exporter)
    monkeypatch.setattr(prometheus_metrics, "is_enabled", lambda: False)

    prometheus_exporter.start_exporter()

    assert prometheus_exporter._exporter_thread is None

    started = threading.Event()

    def fake_export_loop():
        started.set()
        prometheus_exporter._stop_event.wait(timeout=1.0)

    monkeypatch.setattr(prometheus_metrics, "is_enabled", lambda: True)
    monkeypatch.setattr(prometheus_metrics, "validate_startup", lambda: None)
    monkeypatch.setattr(prometheus_exporter, "_export_loop", fake_export_loop)

    prometheus_exporter.start_exporter()
    first_thread = prometheus_exporter._exporter_thread
    prometheus_exporter.start_exporter()

    assert first_thread is not None
    assert prometheus_exporter._exporter_thread is first_thread
    assert started.wait(timeout=1.0)

    prometheus_exporter.stop_exporter()
    prometheus_exporter.stop_exporter()

    assert prometheus_exporter._exporter_thread is None


def test_ops_correlate_accepts_generic_id(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    from observability.correlation import record_request_correlation

    record_request_correlation(
        request_id="req-correlation-1",
        backend="backend-a",
        status="success",
        latency_ms=12,
    )
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get(
        "/v1/ops/correlate?id=req-correlation-1",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target"] == "req-correlation-1"
    assert data["matched_count"] >= 1
