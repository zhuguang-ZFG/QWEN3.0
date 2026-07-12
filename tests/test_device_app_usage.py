"""Tests for routes/device_app_usage.py (/stats/usage)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_app_helpers import headers, seed_account_and_device
from device_gateway.sessions import registry
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.db import _schema_ready_paths, connect
from routes.device_app_usage import _capability_from_intent


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())

    from routes.device_app_usage import router as usage_router

    registry.clear()
    app = FastAPI()
    app.include_router(usage_router, prefix="/device/v1/app")
    return TestClient(app)


def _seed_completed_tasks() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, intent, status) VALUES ('t-draw', 'dev-1', 'a-owner', 'draw_image', 'completed')"
        )
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, intent, status) VALUES ('t-write', 'dev-1', 'a-owner', 'write_text', 'completed')"
        )
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, intent, status) VALUES ('t-chat', 'dev-1', 'a-owner', 'chat', 'completed')"
        )
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, intent, status) VALUES ('t-pending', 'dev-1', 'a-owner', 'draw_image', 'pending')"
        )
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, intent, status) VALUES ('t-other', 'dev-1', 'a-other', 'draw_image', 'completed')"
        )
        conn.commit()


def test_capability_from_intent_classification():
    assert _capability_from_intent("draw_image") == "draw_generated"
    assert _capability_from_intent("write_text") == "write_text"
    assert _capability_from_intent("run_path") == "write_text"
    assert _capability_from_intent("chat") == "chat"
    assert _capability_from_intent("") == "chat"


def test_usage_stats_requires_auth(client):
    response = client.get("/device/v1/app/stats/usage")
    assert response.status_code == 401


def test_usage_stats_aggregates_only_own_completed(client):
    seed_account_and_device()
    _seed_completed_tasks()

    response = client.get("/device/v1/app/stats/usage", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    summary = data["summary"]
    assert summary["totalRequests"] == 3  # excludes pending + other account
    assert summary["totalTokens"] == 1500 + 1000 + 500

    caps = {c["capability"]: c["requests"] for c in data["byCapability"]}
    assert caps == {"draw_generated": 1, "write_text": 1, "chat": 1}

    assert data["details"]["total"] == 3
    assert len(data["details"]["items"]) == 3


def test_usage_stats_pagination(client):
    seed_account_and_device()
    _seed_completed_tasks()

    response = client.get("/device/v1/app/stats/usage?page=1&page_size=2", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    details = response.json()["data"]["details"]
    assert details["total"] == 3
    assert len(details["items"]) == 2
