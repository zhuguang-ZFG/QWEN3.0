"""Tests for routes/admin_extra_agent_tasks.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_auth
from routes import admin_extra_agent_tasks


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin_extra_agent_tasks.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


def test_agent_tasks_store_unavailable(client):
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=None):
        response = client.get("/api/agent-tasks", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["count"] == 0


def test_agent_tasks_list(client):
    store = {
        "task-1": {
            "task_id": "task-1",
            "status": "running",
            "created_at": 1000,
            "request": {"goal": "do something", "description": "desc"},
            "worker_id": "worker-a",
            "backend": "be1",
        },
        "task-2": {
            "task_id": "task-2",
            "status": "pending",
            "created_at": 500,
            "request": {},
            "claim": {"worker_id": "worker-b"},
        },
    }
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=store):
        response = client.get("/api/agent-tasks", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["tasks"][0]["task_id"] == "task-1"


def test_agent_task_detail(client):
    store = {"task-1": {"task_id": "task-1", "status": "running"}}
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=store):
        response = client.get("/api/agent-tasks/task-1", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_agent_task_detail_not_found(client):
    store = {}
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=store):
        response = client.get("/api/agent-tasks/task-1", headers=_auth_headers())
    assert response.status_code == 404


def test_agent_task_detail_store_missing(client):
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=None):
        response = client.get("/api/agent-tasks/task-1", headers=_auth_headers())
    assert response.status_code == 404


def test_cancel_agent_task(client):
    store = {"task-1": {"task_id": "task-1", "status": "running"}}
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=store):
        response = client.post("/api/agent-tasks/task-1/cancel", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancel_requested"
    assert store["task-1"]["status"] == "cancel_requested"


def test_cancel_agent_task_not_found(client):
    store = {}
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=store):
        response = client.post("/api/agent-tasks/task-1/cancel", headers=_auth_headers())
    assert response.status_code == 404


def test_retry_agent_task(client):
    store = {"task-1": {"task_id": "task-1", "status": "failed"}}
    with patch.object(admin_extra_agent_tasks, "_get_task_store", return_value=store):
        response = client.post("/api/agent-tasks/task-1/retry", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert store["task-1"]["status"] == "pending"
