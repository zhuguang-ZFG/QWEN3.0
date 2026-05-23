"""Tests for agent task API routes."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force test token regardless of real env
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from fastapi.testclient import TestClient
from fastapi import FastAPI

from routes.agent_tasks import _reset_for_tests, _store, router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

HEADERS = {"Authorization": "Bearer test-admin-token"}


class TestTaskEndpoints:
    def setup_method(self):
        _reset_for_tests()

    def test_create_task_success(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "fix bug in routing_engine.py",
        }, headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "accepted"

    def test_create_task_unauthorized(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "test",
        }, headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_get_task_not_found(self):
        resp = client.get("/agent/tasks/nonexistent", headers=HEADERS)
        assert resp.status_code == 404

    def test_get_task_events(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "test events",
        }, headers=HEADERS)
        task_id = resp.json()["task_id"]
        resp = client.get(f"/agent/tasks/{task_id}/events", headers=HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()["events"]) >= 1

    def test_get_task_returns_lima_code_task_envelope(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT",
            "goal": "review routing",
            "mode": "review",
            "allowed_tools": ["read", "mcp"],
        }, headers=HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert "task" in data
        assert data["task"]["task_id"] == task_id
        assert data["task"]["repo"] == "D:/GIT"
        assert data["task"]["goal"] == "review routing"
        assert data["task"]["mode"] == "review"
        assert data["task"]["allowed_tools"] == ["read", "mcp"]
        assert data["status"] == "accepted"

    def test_create_task_preserves_patch_files_and_test_commands(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "patch smoke",
            "mode": "patch",
            "allowed_tools": ["write", "git_diff", "test"],
            "patch_files": [{"file_path": "README.md", "content": "# Smoke\n"}],
            "test_commands": ["node test.js"],
        }, headers=HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["task"]["patch_files"] == [
            {"file_path": "README.md", "content": "# Smoke\n"}
        ]
        assert data["task"]["test_commands"] == ["node test.js"]

    def test_list_tasks_filters_status_and_limit_for_worker_polling(self):
        first = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "first accepted",
        }, headers=HEADERS).json()["task_id"]
        second = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "second accepted",
        }, headers=HEADERS).json()["task_id"]
        task = _store.get(first)
        task["status"] = "running"
        _store.update(first)

        resp = client.get("/agent/tasks?status=accepted&limit=1", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == second
        assert data["tasks"][0]["goal"] == "second accepted"

    def test_submit_task_result_updates_status_and_events(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "submit result",
        }, headers=HEADERS).json()["task_id"]
        result = {
            "task_id": task_id,
            "status": "succeeded",
            "summary": "review passed",
            "changed_files": [],
            "test_commands": ["npm.cmd run check"],
            "test_results": [{"command": "npm.cmd run check", "exit_code": 0}],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "",
        }

        resp = client.post(
            f"/agent/tasks/{task_id}/result", json=result, headers=HEADERS
        )

        assert resp.status_code == 200
        assert resp.json()["accepted"] is True
        task_resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)
        assert task_resp.json()["status"] == "succeeded"
        assert task_resp.json()["result"]["summary"] == "review passed"
        events_resp = client.get(f"/agent/tasks/{task_id}/events", headers=HEADERS)
        assert any(
            event["type"] == "result_submitted"
            for event in events_resp.json()["events"]
        )

    def test_claim_task_assigns_worker_and_lease(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "review diff",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-local", "lease_sec": 60},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["task"]["worker_id"] == "worker-local"
        assert data["task"]["lease_expires_at"] > 0
        assert data["status"] == "running"

    def test_claim_task_rejects_active_running_lease(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "review diff",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        first = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-a", "lease_sec": 300},
            headers=HEADERS,
        )
        assert first.status_code == 200

        second = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-b", "lease_sec": 300},
            headers=HEADERS,
        )

        assert second.status_code == 409
        task = client.get(f"/agent/tasks/{task_id}", headers=HEADERS).json()
        assert task["task"]["worker_id"] == "worker-a"

    def test_claim_task_allows_expired_running_lease(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "review diff",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-a", "lease_sec": 1},
            headers=HEADERS,
        )
        task = _store.get(task_id)
        task["request"]["lease_expires_at"] = time.time() - 1
        _store.update(task_id)

        second = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-b", "lease_sec": 300},
            headers=HEADERS,
        )

        assert second.status_code == 200
        assert second.json()["task"]["worker_id"] == "worker-b"

    def test_cancel_task_marks_control_flag(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "test cancel",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.post(f"/agent/tasks/{task_id}/cancel", headers=HEADERS)
        assert resp.status_code == 200

        control = client.get(f"/agent/tasks/{task_id}/control", headers=HEADERS)
        assert control.status_code == 200
        assert control.json()["cancel_requested"] is True
        assert control.json()["status"] == "cancel_requested"

    def test_review_gate_promotes_only_approved_successful_task(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "safe patch",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        result = {
            "task_id": task_id,
            "status": "needs_review",
            "summary": "reviewed",
            "changed_files": [],
            "test_commands": [],
            "test_results": [],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "approve",
        }
        client.post(f"/agent/tasks/{task_id}/result", json=result, headers=HEADERS)

        review = client.post(
            f"/agent/tasks/{task_id}/review",
            json={"decision": "approved", "reviewer": "human"},
            headers=HEADERS,
        )
        assert review.status_code == 200
        assert review.json()["status"] == "approved"

    def test_quarantine_task_updates_status_and_events(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT/deepcode-cli",
            "goal": "bad task",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.post(f"/agent/tasks/{task_id}/quarantine", headers=HEADERS)

        assert resp.status_code == 200
        assert resp.json()["status"] == "quarantined"
        task_resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)
        assert task_resp.json()["status"] == "quarantined"
        events_resp = client.get(f"/agent/tasks/{task_id}/events", headers=HEADERS)
        assert any(
            event["type"] == "quarantined"
            for event in events_resp.json()["events"]
        )

    def test_invalid_mode_rejected(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "test", "mode": "destroy",
        }, headers=HEADERS)
        assert resp.status_code == 422 or resp.status_code == 500


class TestSkillEndpoints:
    def test_list_candidates_empty(self):
        resp = client.get("/agent/skills/candidates", headers=HEADERS)
        assert resp.status_code == 200
        assert "candidates" in resp.json()

    def test_promote_nonexistent_fails(self):
        resp = client.post("/agent/skills/nonexist/promote", json={
            "eval_passed": True, "manual_flag": True,
        }, headers=HEADERS)
        assert resp.status_code == 400

    def test_promote_requires_auth(self):
        resp = client.post("/agent/skills/x/promote", json={
            "eval_passed": True, "manual_flag": True,
        })
        assert resp.status_code in (401, 422)
