"""PROD-008 E2E: HTTP task result triggers learning loop channels."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"
os.environ["LIMA_API_KEY"] = "test-private-token"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.agent_tasks import _reset_for_tests, router as agent_router
from routes.ops_metrics import router as ops_router
from scripts.smoke_prod008_learning_loop_e2e import BACKEND, verify_learning_channels

HEADERS = {"Authorization": "Bearer test-admin-token"}
OPS_HEADERS = {"Authorization": "Bearer test-private-token"}


def _client() -> TestClient:
    app = FastAPI()
    app.state.stats = {"total_requests": 0, "backend_calls": {}, "start_time": 1}
    app.include_router(agent_router)
    app.include_router(ops_router)
    return TestClient(app)


class TestProd008LearningLoopE2E:
    def setup_method(self):
        _reset_for_tests()

    def test_result_submit_feeds_learning_loop_channels(self):
        client = _client()
        metrics_before = client.get("/v1/ops/metrics", headers=OPS_HEADERS).json()
        eval_before = (metrics_before.get("learning") or {}).get("loop", {}).get(
            "eval_candidates", 0
        )

        task_id = client.post(
            "/agent/tasks",
            json={
                "repo": "D:/GIT",
                "goal": "PROD-008 test learning ingest",
                "mode": "review",
            },
            headers=HEADERS,
        ).json()["task_id"]

        resp = client.post(
            f"/agent/tasks/{task_id}/result",
            json={
                "task_id": task_id,
                "status": "needs_review",
                "summary": f"PROD-008 test {task_id}",
                "changed_files": ["session_memory/learning_loop.py"],
                "test_results": [
                    {"command": "pytest", "exit_code": 0, "duration_ms": 50},
                ],
                "artifacts": [f".lima/artifacts/{task_id}/review/summary.md"],
                "backend": BACKEND,
                "latency_ms": 900,
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

        metrics_after = client.get("/v1/ops/metrics", headers=OPS_HEADERS).json()
        eval_after = (metrics_after.get("learning") or {}).get("loop", {}).get(
            "eval_candidates", 0
        )
        assert "loop" in (metrics_after.get("learning") or {})

        report = verify_learning_channels(
            task_id,
            backend=BACKEND,
            eval_before=eval_before,
            eval_after=eval_after,
        )
        assert report["smoke_ok"] is True
        assert report["channels"]["memory"] is True
        assert report["channels"]["prompt"] is True
        assert report["channels"]["routing"] is True
        assert report["channels"]["eval"] is True
