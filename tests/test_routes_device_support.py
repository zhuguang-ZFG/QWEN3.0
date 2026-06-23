"""Tests for routes/device_support.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_support


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-key")
    app = FastAPI()
    app.include_router(device_support.router)
    return TestClient(app)


@patch("routes.device_support.build_support_snapshot")
def test_get_snapshot_requires_auth(mock_snapshot, client):
    mock_snapshot.return_value = {"device_id": "d1", "active_tasks": 0}
    response = client.get("/device/v1/support/d1/snapshot")
    assert response.status_code == 401
    mock_snapshot.assert_not_called()


@patch("routes.device_support.build_support_snapshot")
def test_get_snapshot_with_bearer(mock_snapshot, client):
    mock_snapshot.return_value = {
        "device_id": "d1",
        "active_tasks": 2,
        "recommendation": "设备运行正常，无需干预。",
    }
    response = client.get(
        "/device/v1/support/d1/snapshot",
        headers={"Authorization": "Bearer test-private-key"},
    )
    assert response.status_code == 200
    assert response.json() == mock_snapshot.return_value
    mock_snapshot.assert_called_once_with("d1")
