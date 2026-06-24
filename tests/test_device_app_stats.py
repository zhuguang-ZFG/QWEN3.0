"""Tests for device app statistics routes."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.sessions import registry
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt
from device_logic.db import _schema_ready_paths, connect
from routes.device_app_stats import router as stats_router


def _token(account_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def _headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(account_id)}"}


def _iso(days_ago: int, hour: int = 12) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=0)
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())
    registry.clear()
    app = FastAPI()
    app.include_router(stats_router)
    return TestClient(app)


def _seed_accounts_devices():
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-other', '13002', 'other')")
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver)
            VALUES ('dev-1', 'SN-APP-01', 'esp32s3_xyz', '1.0.0', 'rev-a'),
                   ('dev-2', 'SN-APP-02', 'esp32s3_xyz', '1.0.0', 'rev-a')
            """
        )
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES ('b-1', 'dev-1', 'a-owner', 'owner', 'active'),
                   ('b-2', 'dev-2', 'a-owner', 'owner', 'active')
            """
        )
        conn.commit()


def _insert_task(task_id, device_id, account_id, intent, status, created_at, started_at=None, completed_at=None):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_task
            (id, device_id, account_id, intent, status, created_at, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, device_id, account_id, intent, status, created_at, started_at, completed_at),
        )
        conn.commit()


def test_device_stats_shape(client):
    _seed_accounts_devices()
    _insert_task("t1", "dev-1", "a-owner", "draw_image", "completed", _iso(1, 10), _iso(1, 10), _iso(1, 11))
    _insert_task("t2", "dev-1", "a-owner", "draw_image", "completed", _iso(1, 14), _iso(1, 14), _iso(1, 15))
    _insert_task("t3", "dev-1", "a-owner", "run_path", "failed", _iso(2, 9))
    _insert_task("t4", "dev-1", "a-owner", "home", "cancelled", _iso(2, 20))

    resp = client.get("/device/v1/app/devices/dev-1/stats", headers=_headers("a-owner"))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["deviceId"] == "dev-1"
    assert data["period"] == "7d"
    assert data["totalTasks"] == 4
    assert data["completedTasks"] == 2
    assert data["failedTasks"] == 1
    assert data["cancelledTasks"] == 1
    assert data["successRate"] == 50.0
    assert data["mostUsedCapability"] == "draw_image"
    assert len(data["dailyBreakdown"]) >= 2
    assert len(data["hourlyPattern"]) == 24
    assert data["hourlyPattern"][10] == 1
    assert data["hourlyPattern"][14] == 1
    assert data["hourlyPattern"][9] == 1
    assert data["hourlyPattern"][20] == 1
    assert data["totalDurationMs"] == 2 * 3600000
    assert data["avgDurationMs"] == 3600000


def test_overview_shape(client):
    _seed_accounts_devices()
    _insert_task("t1", "dev-1", "a-owner", "draw_image", "completed", _iso(1), _iso(1), _iso(1))
    _insert_task("t2", "dev-1", "a-owner", "run_path", "completed", _iso(2), _iso(2), _iso(2))
    _insert_task("t3", "dev-2", "a-owner", "home", "failed", _iso(1))

    resp = client.get("/device/v1/app/stats/overview", headers=_headers("a-owner"))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["accountId"] == "a-owner"
    assert data["totalDevices"] == 2
    assert data["activeDevices"] == 2
    assert data["totalTasks"] == 3
    assert data["completedTasks"] == 2
    assert data["failedTasks"] == 1
    assert data["successRate"] == pytest.approx(66.7, 0.1)
    ranking = data["deviceRanking"]
    assert len(ranking) == 2
    assert ranking[0]["deviceId"] == "dev-1"
    assert ranking[0]["taskCount"] == 2
    assert ranking[1]["deviceId"] == "dev-2"
    assert ranking[1]["taskCount"] == 1


def test_period_filtering(client):
    _seed_accounts_devices()
    old = _iso(80, 8)
    recent = _iso(2, 8)
    _insert_task("t-old", "dev-1", "a-owner", "draw_image", "completed", old, old, old)
    _insert_task("t-recent", "dev-1", "a-owner", "home", "completed", recent, recent, recent)

    resp_7d = client.get("/device/v1/app/devices/dev-1/stats?period=7d", headers=_headers("a-owner"))
    data_7d = resp_7d.json()["data"]
    assert data_7d["totalTasks"] == 1

    resp_90d = client.get("/device/v1/app/devices/dev-1/stats?period=90d", headers=_headers("a-owner"))
    data_90d = resp_90d.json()["data"]
    assert data_90d["totalTasks"] == 2

    overview_7d = client.get("/device/v1/app/stats/overview?period=7d", headers=_headers("a-owner")).json()["data"]
    assert overview_7d["totalTasks"] == 1
    overview_90d = client.get("/device/v1/app/stats/overview?period=90d", headers=_headers("a-owner")).json()["data"]
    assert overview_90d["totalTasks"] == 2


def test_access_denied(client):
    _seed_accounts_devices()
    _insert_task("t1", "dev-1", "a-owner", "draw_image", "completed", _iso(1), _iso(1), _iso(1))

    resp = client.get("/device/v1/app/devices/dev-1/stats", headers=_headers("a-other"))
    assert resp.status_code == 403
    assert resp.json()["code"] == 403


def test_empty_stats(client):
    _seed_accounts_devices()
    resp = client.get("/device/v1/app/devices/dev-1/stats", headers=_headers("a-owner"))
    data = resp.json()["data"]
    assert data["totalTasks"] == 0
    assert data["successRate"] == 0.0
    assert data["mostUsedCapability"] is None
    assert data["dailyBreakdown"] == []
    assert data["hourlyPattern"] == [0] * 24
