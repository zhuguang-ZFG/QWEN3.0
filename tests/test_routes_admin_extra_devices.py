"""Tests for routes/admin_extra_devices.py."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_extra_devices


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin_extra_devices.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


def _registry_module(**funcs):
    return SimpleNamespace(**funcs)


def test_admin_devices_registry(client):
    fake = _registry_module(get_all_devices=lambda: [{"device_id": "d1"}])
    with patch.dict(sys.modules, {"device_gateway.registry": fake}):
        response = client.get("/api/devices", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["device_id"] == "d1"


def test_admin_devices_fallback(client):
    fake_registry = _registry_module(get_all_devices=lambda: (_ for _ in ()).throw(ImportError()))
    fake_store = _registry_module(task_store_health=lambda: {"ok": True})
    with patch.dict(sys.modules, {"device_gateway.registry": fake_registry, "device_gateway.store": fake_store}):
        response = client.get("/api/devices", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["devices"] == []
    assert "task_store only" in data["_note"]


def test_admin_device_detail(client):
    fake = _registry_module(get_device=lambda device_id: {"device_id": device_id, "status": "online"})
    with patch.dict(sys.modules, {"device_gateway.registry": fake}):
        response = client.get("/api/devices/d1", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["device_id"] == "d1"


def test_admin_device_detail_not_found(client):
    fake = _registry_module(get_device=lambda _device_id: None)
    with patch.dict(sys.modules, {"device_gateway.registry": fake}):
        response = client.get("/api/devices/d1", headers=_auth_headers())
    assert response.status_code == 404


def test_admin_device_detail_gateway_unavailable(client):
    fake = _registry_module(get_device=lambda _device_id: (_ for _ in ()).throw(ImportError()))
    with patch.dict(sys.modules, {"device_gateway.registry": fake}):
        response = client.get("/api/devices/d1", headers=_auth_headers())
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_admin_restart_device(client):
    async def mock_restart(device_id):
        return None

    fake = _registry_module(restart_device=mock_restart)
    with patch.dict(sys.modules, {"device_gateway.registry": fake}):
        response = client.post("/api/devices/d1/restart", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["device_id"] == "d1"


def test_admin_restart_device_unavailable(client):
    fake = _registry_module(restart_device=lambda _device_id: (_ for _ in ()).throw(ImportError()))
    with patch.dict(sys.modules, {"device_gateway.registry": fake}):
        response = client.post("/api/devices/d1/restart", headers=_auth_headers())
    assert response.status_code == 503
