from fastapi import FastAPI
from fastapi.testclient import TestClient

import server
from routes.ops_metrics import router


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


def test_eval_approve_marks_candidate_manual_approved(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setenv("LIMA_SESSION_DB", str(tmp_path / "memory.db"))

    from session_memory.store import save_typed_memory

    save_typed_memory(
        "reference_pattern",
        "candidate:backend-a:coding - 3 successes",
        detail='{"backend":"backend-a","scenario":"coding","evidence_count":3,"latest_task":"task-3","status":"needs_approval"}',
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    approve = client.post(
        "/v1/ops/eval/approve",
        json={"pattern_key": "backend-a:coding", "rollback_notes": "remove from prompt profile"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert approve.status_code == 200
    assert approve.json()["approved"] is True

    revision = client.get(
        "/v1/ops/eval/revision",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert revision.status_code == 200
    data = revision.json()
    assert any(c["pattern_key"] == "backend-a:coding" for c in data["promotable"])


def test_eval_apply_is_idempotent_after_recent_memory_noise(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    import session_memory.store as memory_store
    import context_pipeline.routing_weights as routing_weights

    monkeypatch.setattr(memory_store, "_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setattr(routing_weights, "WEIGHTS_PATH", tmp_path / "weights.json")
    monkeypatch.setattr(routing_weights, "_instance", None)

    from session_memory.store import save_typed_memory
    from context_pipeline.routing_weights import get_routing_weights

    save_typed_memory(
        "reference_pattern",
        "candidate:backend-a:coding - 3 successes",
        detail='{"pattern_key":"backend-a:coding","backend":"backend-a","scenario":"coding","evidence_count":3}',
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    approve = client.post(
        "/v1/ops/eval/approve",
        json={"pattern_key": "backend-a:coding", "rollback_notes": "rollback"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert approve.status_code == 200

    first = client.post(
        "/v1/ops/eval/apply",
        json={"pattern_key": "backend-a:coding"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert first.status_code == 200
    assert first.json()["applied"] is True

    for index in range(35):
        save_typed_memory("reference_pattern", f"noise:{index}", detail="{}")

    second = client.post(
        "/v1/ops/eval/apply",
        json={"pattern_key": "backend-a:coding"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert second.status_code == 200
    assert second.json() == {
        "applied": False,
        "error": "pattern already promoted",
        "pattern_key": "backend-a:coding",
    }
    assert get_routing_weights().get_stats("backend-a", "coding")["successes"] == 3


def test_eval_apply_rejects_non_object_body(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post(
        "/v1/ops/eval/apply",
        json=["backend-a:coding"],
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "JSON object body required"


def test_eval_apply_rejects_malformed_json(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post(
        "/v1/ops/eval/apply",
        content='["bad\\"]',
        headers={
            "Authorization": "Bearer test-private-token",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "valid JSON body required"


def test_ops_metrics_includes_recent_agent_tasks(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

    import routes.agent_tasks as agent_tasks

    agent_tasks._DB_PATH = str(tmp_path / "agent_tasks.db")
    agent_tasks._store = agent_tasks._TaskStore(agent_tasks._DB_PATH)
    agent_tasks._reset_for_tests()

    from routes.agent_tasks import TaskCreateBody, _create_task_from_body

    created = _create_task_from_body(TaskCreateBody(
        repo="D:/GIT/deepcode-cli",
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
