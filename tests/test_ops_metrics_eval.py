"""Ops eval approve/apply tests."""

import builtins
import importlib
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import server
from routes.ops_metrics import router

from ops_metrics_helpers import reload_prometheus_metrics


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


def _setup_eval_test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    import session_memory.store as memory_store
    import context_pipeline.routing_weights as routing_weights

    monkeypatch.setattr(memory_store, "_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setattr(routing_weights, "WEIGHTS_PATH", tmp_path / "weights.json")
    monkeypatch.setattr(routing_weights, "_instance", None)


def _seed_candidate_pattern() -> None:
    from session_memory.store import save_typed_memory

    save_typed_memory(
        "reference_pattern",
        "candidate:backend-a:coding - 3 successes",
        detail='{"pattern_key":"backend-a:coding","backend":"backend-a","scenario":"coding","evidence_count":3}',
    )


def _approve_pattern(client) -> None:
    approve = client.post(
        "/v1/ops/eval/approve",
        json={"pattern_key": "backend-a:coding", "rollback_notes": "rollback"},
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert approve.status_code == 200


def _apply_pattern(client):
    return client.post(
        "/v1/ops/eval/apply",
        json={"pattern_key": "backend-a:coding"},
        headers={"Authorization": "Bearer test-private-token"},
    )


def test_eval_apply_is_idempotent_after_recent_memory_noise(monkeypatch, tmp_path):
    _setup_eval_test_env(monkeypatch, tmp_path)
    _seed_candidate_pattern()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    _approve_pattern(client)

    first = _apply_pattern(client)
    assert first.status_code == 200
    assert first.json()["applied"] is True

    from session_memory.store import save_typed_memory

    for index in range(35):
        save_typed_memory("reference_pattern", f"noise:{index}", detail="{}")

    second = _apply_pattern(client)
    assert second.status_code == 200
    assert second.json() == {
        "applied": False,
        "error": "pattern already promoted",
        "pattern_key": "backend-a:coding",
    }

    from context_pipeline.routing_weights import get_routing_weights

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
