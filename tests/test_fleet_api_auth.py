"""HTTP-level tests for /fleet/* token authentication."""

from __future__ import annotations

import time

import pytest

MOCK_NOW = 2_000_000_000.0


class TestFleetAPIAuth:
    """HTTP-level tests for /fleet/* token authentication."""

    def _make_app(self, admin_token: str = ""):
        from fastapi import FastAPI
        from routes.fleet_api import router, inject_state

        inject_state(admin_token=admin_token)
        app = FastAPI()
        app.include_router(router)
        return app

    def _client(self, admin_token: str = ""):
        from fastapi.testclient import TestClient

        return TestClient(self._make_app(admin_token))

    def test_no_token_configured_returns_503(self):
        """When server has no fleet token, all endpoints must reject."""
        resp = self._client(admin_token="").get("/fleet/nodes")
        assert resp.status_code == 503

    def test_missing_auth_header_returns_401(self):
        resp = self._client(admin_token="secret123").get("/fleet/nodes")
        assert resp.status_code == 401

    def test_invalid_bearer_token_returns_401(self):
        client = self._client(admin_token="secret123")
        resp = client.get("/fleet/nodes", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_valid_bearer_token_accepted(self):
        client = self._client(admin_token="secret123")
        resp = client.get("/fleet/nodes", headers={"Authorization": "Bearer secret123"})
        assert resp.status_code == 200

    def test_x_fleet_token_header_accepted(self):
        client = self._client(admin_token="secret123")
        resp = client.get("/fleet/nodes", headers={"X-Fleet-Token": "secret123"})
        assert resp.status_code == 200

    def test_register_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/register", json={"node_id": "n1"})
        assert resp.status_code == 401

    def test_submit_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/submit", json={"task_type": "shell"})
        assert resp.status_code == 401

    def test_poll_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.get("/fleet/poll/n1")
        assert resp.status_code == 401

    def test_complete_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/complete", json={"task_id": "t1"})
        assert resp.status_code == 401

    def test_heartbeat_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/heartbeat", json={"node_id": "n1"})
        assert resp.status_code == 401


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
