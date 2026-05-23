"""Tests for agent task API routes."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force test token regardless of real env
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from fastapi.testclient import TestClient
from fastapi import FastAPI

from routes.agent_tasks import _events, _tasks, router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

HEADERS = {"Authorization": "Bearer test-admin-token"}


class TestTaskEndpoints:
    def setup_method(self):
        _tasks.clear()
        _events.clear()

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

    def test_list_tasks_filters_status_and_limit_for_worker_polling(self):
        first = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "first accepted",
        }, headers=HEADERS).json()["task_id"]
        second = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "second accepted",
        }, headers=HEADERS).json()["task_id"]
        _tasks[first]["status"] = "running"

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
