"""Tests for routes/device_memory.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_memory as dm


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(dm.router)
    return TestClient(app)


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture(autouse=True)
def _patch_memory_store(mock_store):
    with patch.object(dm, "get_memory_store", return_value=mock_store):
        yield


def test_get_planner_hints_requires_auth(client):
    assert client.get("/device/v1/memory/dev-1/hints").status_code == 401


def test_get_planner_hints(client, mock_store):
    mock_store.list_by_device.return_value = []
    with patch.object(dm, "recall_planner_hints", return_value=["hint-1"]) as mock_recall:
        response = client.get("/device/v1/memory/dev-1/hints", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["hints"] == ["hint-1"]
    mock_recall.assert_called_once_with(mock_store, "dev-1")


def test_get_warnings(client, mock_store):
    with patch.object(dm, "get_device_failure_warnings", return_value=["warn-1"]) as mock_warnings:
        response = client.get("/device/v1/memory/dev-1/warnings", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["warnings"] == ["warn-1"]
    mock_warnings.assert_called_once_with(mock_store, "dev-1")


def test_list_memories(client, mock_store):
    entry = MagicMock()
    entry.model_dump.return_value = {"id": "e1", "device_id": "dev-1"}
    mock_store.list_by_device.return_value = [entry]
    response = client.get("/device/v1/memory/dev-1/list", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["entries"] == [{"id": "e1", "device_id": "dev-1"}]


def test_reset_memories(client, mock_store):
    mock_store.reset.return_value = 5
    response = client.delete("/device/v1/memory/dev-1/reset", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["deleted"] == 5
    mock_store.reset.assert_called_once_with("dev-1")


def test_disable_memory_missing_entry_id(client):
    response = client.post(
        "/device/v1/memory/dev-1/disable",
        json={},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400
    assert "entry_id" in response.json()["detail"]


def test_disable_memory(client, mock_store):
    mock_store.disable.return_value = True
    response = client.post(
        "/device/v1/memory/dev-1/disable",
        json={"entry_id": "e1"},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["disabled"] is True
    mock_store.disable.assert_called_once_with("e1")


def test_export_memories(client, mock_store):
    mock_store.export.return_value = '{"data": "value"}'
    response = client.post("/device/v1/memory/dev-1/export", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["data"] == '{"data": "value"}'
    mock_store.export.assert_called_once_with("dev-1")


def test_trigger_consolidation(client, mock_store):
    entry = MagicMock()
    entry.model_dump.return_value = {"id": "e2"}
    with patch.object(dm, "consolidate_task_episodes", return_value=[entry]) as mock_consolidate:
        response = client.post(
            "/device/v1/memory/dev-1/consolidate", headers={"Authorization": "Bearer test-key"}
        )
    assert response.status_code == 200
    assert response.json()["consolidated"] == 1
    mock_consolidate.assert_called_once_with(mock_store, "dev-1")
