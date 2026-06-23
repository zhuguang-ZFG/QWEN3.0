"""Tests for routes/admin_extra_agent_tasks.py — agent task admin routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routes.admin_extra_agent_tasks import router as agent_tasks_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(agent_tasks_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify
app.dependency_overrides[admin_auth.verify_csrf] = _noop_verify


class TestAgentTasks:
    def test_list_empty_when_store_unavailable(self):
        client = TestClient(app)
        with patch("routes.admin_extra_agent_tasks._get_task_store", return_value=None):
            response = client.get("/api/agent-tasks")
            assert response.status_code == 200
            assert response.json()["tasks"] == []

    def test_list_tasks(self):
        client = TestClient(app)
        store = {
            "t1": {
                "task_id": "t1",
                "status": "running",
                "created_at": 1000,
                "request": {"goal": "test task"},
                "worker_id": "w1",
            }
        }
        with patch("routes.admin_extra_agent_tasks._get_task_store", return_value=store):
            response = client.get("/api/agent-tasks")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["tasks"][0]["task_id"] == "t1"

    def test_detail_not_found(self):
        client = TestClient(app)
        store = {}
        with patch("routes.admin_extra_agent_tasks._get_task_store", return_value=store):
            response = client.get("/api/agent-tasks/missing")
            assert response.status_code == 404

    def test_cancel_task(self):
        client = TestClient(app)
        store = {"t1": {"task_id": "t1", "status": "running"}}
        with patch("routes.admin_extra_agent_tasks._get_task_store", return_value=store):
            response = client.post("/api/agent-tasks/t1/cancel")
            assert response.status_code == 200
            assert store["t1"]["status"] == "cancel_requested"
