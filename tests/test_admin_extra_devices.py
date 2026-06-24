"""Tests for routes/admin_extra_devices.py — device gateway inspection."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin_extra_devices import router as devices_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(devices_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify


class TestAdminDevices:
    def test_list_devices(self):
        client = TestClient(app)
        response = client.get("/api/devices")
        assert response.status_code == 200
        assert "devices" in response.json()

    def test_device_detail_not_found(self):
        client = TestClient(app)
        response = client.get("/api/devices/nonexistent")
        assert response.status_code == 404
