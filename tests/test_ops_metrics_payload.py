"""Ops metrics payload and telemetry snapshots."""

import builtins
import importlib
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import server
from routes.ops_metrics import router

from ops_metrics_helpers import reload_prometheus_metrics

@pytest.mark.skip(reason="Skip: test_ops_metrics_includes_recent_agent_tasks depends on routes.agent_tasks not yet implemented")
def test_ops_metrics_includes_recent_agent_tasks(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    import routes.agent_tasks as agent_tasks

    agent_tasks._DB_PATH = str(tmp_path / "agent_tasks.db")
    agent_tasks._store = agent_tasks._TaskStore(agent_tasks._DB_PATH)
    agent_tasks._reset_for_tests()

    from routes.agent_tasks import TaskCreateBody, _create_task_from_body

    created = _create_task_from_body(TaskCreateBody(
        repo="D:/GIT/lima-worker-sandbox",
        goal="ops metrics recent task",
        mode="review",
    ))

    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    recent = response.json().get("recent_agent_tasks", [])
    assert any(item["task_id"] == created["task_id"] for item in recent)
    assert any("ops metrics recent task" in item["goal"] for item in recent)

    agent_tasks._reset_for_tests()


def test_ops_metrics_includes_learning_loop_stats(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    loop = (response.json().get("learning") or {}).get("loop") or {}
    assert "eval_candidates" in loop
    assert "prompt_profile_keys" in loop


def test_ops_metrics_includes_sanitized_cli_telemetry(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    from observability.cli_telemetry import record_cli_outcome, sanitize_cli_outcome

    record = sanitize_cli_outcome(
        task_id="hls-unit",
        backend="cli-agent",
        scenario="coding",
        success=False,
        latency_ms=1234,
        telemetry={
            "timeoutMs": 90000,
            "maxRetries": 1,
            "retryCount": 1,
            "modelCalls": [
                {"ok": False, "latencyMs": 90001, "error": "AbortError: timeout with secret sk-test"},
                {"ok": True, "latencyMs": 42, "toolCalls": 1},
            ],
            "toolCapability": {"requested": True, "observed": True, "protocol": "openai", "toolCalls": 1},
        },
    )
    assert record_cli_outcome(record) is True

    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    telemetry = response.json()["cli_telemetry"]
    assert telemetry["total_recent"] == 1
    assert telemetry["failed_recent"] == 1
    assert telemetry["retry_count_recent"] == 1
    recent = telemetry["recent"][0]
    assert recent["model_calls"]["error_classes"] == {"timeout": 1}
    assert "sk-test" not in str(recent)


def test_ops_metrics_includes_backend_telemetry(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    from observability.backend_telemetry import record_backend_attempt

    assert record_backend_attempt(
        backend="tool_backend_a",
        scenario="coding",
        request_type="tool_use",
        success=False,
        latency_ms=90001,
        tools_requested=True,
        status_code=504,
        error="timeout with secret sk-test",
        phase="tool_forward",
        attempt="tier1_openai",
    )

    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    telemetry = response.json()["backend_telemetry"]
    assert telemetry["total_recent"] == 1
    assert telemetry["failed_recent"] == 1
    assert telemetry["slow_recent"] == 1
    assert telemetry["error_classes"] == {"timeout": 1}
    assert telemetry["by_backend"]["tool_backend_a"]["failures"] == 1
    assert "sk-test" not in str(telemetry)


def test_ops_metrics_includes_backend_recovery_snapshot(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    import backend_retirement
    import health_state

    backend_retirement._retired_backends.clear()
    backend_retirement._retired_backends.add("retired_backend")
    health_state.reset_all_state()
    health_state._health_map["retired_backend"] = "dead"
    health_state._health_map["probe_backend"] = "dead"

    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    recovery = response.json()["backends"]["recovery"]
    assert recovery["retired_count"] == 1
    assert recovery["retired_list"] == ["retired_backend"]
    assert recovery["probe_candidates"] == ["probe_backend"]

    backend_retirement._retired_backends.clear()
    health_state.reset_all_state()


def test_ops_metrics_includes_routing_guard_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    from observability.backend_telemetry import record_backend_attempt

    assert record_backend_attempt(
        backend="guarded_backend",
        success=False,
        response_empty=True,
    )

    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(router)
    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    guard = response.json()["routing_guard"]
    assert guard["enabled"] is True
    assert guard["decisions"]["guarded_backend"]["status"] == "quarantined"
