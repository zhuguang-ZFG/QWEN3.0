"""Tests for device gateway admin endpoints (Phase 3.1)."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from routes.admin_api import router as admin_api_router
from routes.admin_auth import verify_admin, verify_csrf

app = FastAPI()
app.dependency_overrides[verify_admin] = lambda: None
app.dependency_overrides[verify_csrf] = lambda: None
app.include_router(admin_api_router, prefix="/admin")
client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-admin-token"}


# -- Helpers ---------------------------------------------------------------

class _FakeSession:
    def __init__(self, device_id: str, fw_rev: str = "1.0"):
        self.device_id = device_id
        self.fw_rev = fw_rev
        self.capabilities = ["mqtt", "restart"]
        self.last_uptime_ms = 120000
        self.inflight_count = 1
        self.inflight_tasks: dict = {}
        self.inflight_lock = MagicMock()

    async def send_json(self, data: dict) -> None:
        pass  # No-op for tests


class _FakeRegistry:
    def __init__(self, sessions: dict[str, _FakeSession] | None = None):
        self._sessions = sessions or {}
        self._lock = MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def items(self):
        return self._sessions.items()

    def get(self, device_id):
        return self._sessions.get(device_id)


_mock_registry = _FakeRegistry({
    "esp32-01": _FakeSession("esp32-01", "2.1"),
    "esp32-02": _FakeSession("esp32-02", "1.8"),
})


@pytest.fixture(autouse=True)
def _inject_registry():
    """Replace device_gateway.sessions.registry with fake."""
    with patch.dict(
        "sys.modules",
        {"device_gateway.sessions": MagicMock(registry=_mock_registry)},
    ):
        yield


# -- List devices ----------------------------------------------------------

def test_devices_list():
    resp = client.get("/admin/api/devices", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    ids = [d["device_id"] for d in data["devices"]]
    assert "esp32-01" in ids
    assert "esp32-02" in ids


# -- Device detail ---------------------------------------------------------

def test_device_detail():
    resp = client.get("/admin/api/devices/esp32-01", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "esp32-01"
    assert data["fw_rev"] == "2.1"


def test_device_detail_not_found():
    resp = client.get("/admin/api/devices/nonexistent", headers=HEADERS)
    assert resp.status_code == 404


# -- Restart ---------------------------------------------------------------

def test_device_restart():
    resp = client.post("/admin/api/devices/esp32-01/restart", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "esp32-01"
    assert data["command"] == "restart"
    assert data["sent"] is True


def test_device_restart_not_found():
    resp = client.post("/admin/api/devices/nonexistent/restart", headers=HEADERS)
    assert resp.status_code == 404
