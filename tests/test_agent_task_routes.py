"""Tests for agent task API routes."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force test token regardless of real env
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from fastapi.testclient import TestClient
from fastapi import FastAPI

from routes.agent_tasks import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

HEADERS = {"Authorization": "Bearer test-admin-token"}


class TestTaskEndpoints:
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
