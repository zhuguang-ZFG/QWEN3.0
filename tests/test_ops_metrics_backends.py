"""Ops backend retire/probe/summary tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.ops_metrics import router


def test_ops_summary_rolls_up_alerts_and_actions(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    import backend_retirement
    import health_state

    backend_retirement._retired_backends.clear()
    backend_retirement._retired_backends.add("retired_backend")
    health_state.reset_all_state()
    health_state._health_map["dead_backend"] = "dead"
    health_state._health_map["degraded_backend"] = "degraded"

    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/summary",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "critical"
    assert data["counts"]["dead_backends"] == 1
    assert data["counts"]["degraded_backends"] == 1
    assert data["counts"]["retired_backends"] == 1
    assert data["actions"]["reactivate_backend"] == "POST /v1/ops/backends/reactivate"
    assert any(alert["code"] == "backend_dead" for alert in data["alerts"])

    backend_retirement._retired_backends.clear()
    health_state.reset_all_state()


def test_ops_backend_manual_retire_and_reactivate(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    import backend_retirement
    import health_state

    backend_retirement.DB_PATH = str(tmp_path / "retirement.db")
    backend_retirement._retired_backends.clear()
    health_state.reset_all_state()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    retire = client.post(
        "/v1/ops/backends/retire",
        json={"backend": "manual_backend", "reason": "operator saw repeated 504"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert retire.status_code == 200
    assert retire.json() == {"ok": True, "backend": "manual_backend", "status": "retired"}
    assert backend_retirement.is_retired("manual_backend")

    reactivate = client.post(
        "/v1/ops/backends/reactivate",
        json={"backend": "manual_backend", "evidence": "fresh probe succeeded"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert reactivate.status_code == 200
    assert reactivate.json() == {"ok": True, "backend": "manual_backend", "status": "healthy"}
    assert not backend_retirement.is_retired("manual_backend")

    backend_retirement._retired_backends.clear()
    health_state.reset_all_state()


def test_ops_backend_reactivate_requires_evidence(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post(
        "/v1/ops/backends/reactivate",
        json={"backend": "manual_backend"},
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "evidence required"


def test_ops_backend_probe_records_without_reactivating(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    calls = {"probe": 0, "reactivate": 0}

    def fake_probe(
        backend: str,
        *,
        ignore_cooldown: bool = False,
        timeout_sec: float | None = None,
    ) -> dict:
        calls["probe"] += 1
        assert ignore_cooldown is True
        assert timeout_sec == 25
        return {
            "backend": backend,
            "status": "healthy",
            "latency_ms": 12,
            "response_len": 2,
            "recorded": True,
        }

    def fake_reactivate(backend: str) -> None:
        calls["reactivate"] += 1

    monkeypatch.setattr("backend_probe_loop.probe_and_record_backend", fake_probe)
    monkeypatch.setattr("backend_retirement.reactivate", fake_reactivate)

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/v1/ops/backends/probe",
        json={"backend": "manual_backend"},
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["reactivated"] is False
    assert data["recommended_action"] == "reactivate_with_evidence"
    assert data["probe"]["recorded"] is True
    assert calls == {"probe": 1, "reactivate": 0}


def test_ops_backend_probe_can_reactivate_on_success(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    calls = {"reactivate": []}

    monkeypatch.setattr(
        "backend_probe_loop.probe_and_record_backend",
        lambda backend, *, ignore_cooldown=False, timeout_sec=None: {
            "backend": backend,
            "status": "healthy",
            "latency_ms": 10,
            "recorded": True,
            "ignore_cooldown": ignore_cooldown,
            "timeout_sec": timeout_sec,
        },
    )
    monkeypatch.setattr(
        "backend_retirement.reactivate",
        lambda backend: calls["reactivate"].append(backend),
    )

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/v1/ops/backends/probe",
        json={"backend": "manual_backend", "reactivate_on_success": True},
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    assert response.json()["reactivated"] is True
    assert response.json()["recommended_action"] == "reactivated"
    assert calls["reactivate"] == ["manual_backend"]


def test_ops_backend_probe_keeps_failed_backend_retired(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setattr(
        "backend_probe_loop.probe_and_record_backend",
        lambda backend, *, ignore_cooldown=False, timeout_sec=None: {
            "backend": backend,
            "status": "failed",
            "latency_ms": 90000,
            "error_class": "timeout",
            "recorded": True,
            "ignore_cooldown": ignore_cooldown,
            "timeout_sec": timeout_sec,
        },
    )

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/v1/ops/backends/probe",
        json={"backend": "manual_backend", "reactivate_on_success": True},
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["reactivated"] is False
    assert response.json()["recommended_action"] == "keep_retired"


def test_ops_backend_probe_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post(
        "/v1/ops/backends/probe",
        json={"backend": "manual_backend", "timeout_sec": 0},
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "timeout_sec must be between 0 and 120"
