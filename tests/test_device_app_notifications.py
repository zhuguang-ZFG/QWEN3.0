import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.sessions import registry
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt
from device_logic.db import _schema_ready_paths, connect


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


def _seed_account_and_device(device_id: str = "dev-1", device_sn: str = "SN-APP-01") -> None:
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-other', '13002', 'other')")
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver)
            VALUES (?, ?, 'esp32s3_xyz', '1.0.0', 'rev-a')
            """,
            (device_id, device_sn),
        )
        conn.commit()


def _seed_binding(device_id: str = "dev-1", account_id: str = "a-owner") -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES ('b-1', ?, ?, 'owner', 'active')
            """,
            (device_id, account_id),
        )
        conn.commit()


def _make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())

    from routes.device_app_api import router as app_router
    from routes.device_app_auth import router as auth_router
    from routes.device_app_notifications import router as notifications_router

    registry.clear()
    app = FastAPI()
    app.include_router(app_router)
    app.include_router(auth_router)
    app.include_router(notifications_router)
    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    return _make_client(tmp_path, monkeypatch)


def test_subscribe_list_unsubscribe_flow(client):
    _seed_account_and_device()
    _seed_binding()
    with connect() as conn:
        conn.execute("UPDATE v2_account SET wechat_openid='wx-openid-1' WHERE id='a-owner'")
        conn.commit()

    response = client.post(
        "/device/v1/app/notifications/subscribe",
        headers=_headers("a-owner"),
        json={
            "openid": "wx-openid-1",
            "templateIds": ["task_completed", "task_failed"],
            "deviceIds": ["dev-1"],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "active"
    sub_id = data["subscriptionId"]
    assert sub_id

    listed = client.get("/device/v1/app/notifications/subscriptions", headers=_headers("a-owner"))
    assert listed.status_code == 200, listed.text
    subscriptions = listed.json()["data"]["subscriptions"]
    assert len(subscriptions) == 1
    assert subscriptions[0]["subscriptionId"] == sub_id
    assert subscriptions[0]["deviceIds"] == ["dev-1"]
    assert subscriptions[0]["templateIds"] == ["task_completed", "task_failed"]

    deleted = client.delete(
        f"/device/v1/app/notifications/subscriptions/{sub_id}",
        headers=_headers("a-owner"),
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["status"] == "unsubscribed"

    listed_after = client.get("/device/v1/app/notifications/subscriptions", headers=_headers("a-owner"))
    assert listed_after.json()["data"]["count"] == 0


def test_subscribe_requires_templates(client):
    _seed_account_and_device()
    with connect() as conn:
        conn.execute("UPDATE v2_account SET wechat_openid='wx-openid-1' WHERE id='a-owner'")
        conn.commit()
    response = client.post(
        "/device/v1/app/notifications/subscribe",
        headers=_headers("a-owner"),
        json={"openid": "wx-openid-1"},
    )
    assert response.status_code == 400, response.text
    assert "templateIds" in response.json()["message"]


def test_subscribe_rejects_without_linked_openid(client):
    _seed_account_and_device()
    _seed_binding()
    response = client.post(
        "/device/v1/app/notifications/subscribe",
        headers=_headers("a-owner"),
        json={
            "openid": "wx-arbitrary",
            "templateIds": ["task_completed"],
            "deviceIds": ["dev-1"],
        },
    )
    assert response.status_code == 400, response.text
    assert "not linked" in response.json()["message"].lower()


def test_subscribe_rejects_unauthorized(client):
    response = client.post("/device/v1/app/notifications/subscribe", json={"openid": "x", "templateIds": ["t"]})
    assert response.status_code == 401, response.text


def test_unsubscribe_only_affects_own_subscription(client):
    _seed_account_and_device()
    _seed_binding()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_notification_subscription
            (id, account_id, openid, template_ids, device_ids, created_at, updated_at, status)
            VALUES ('sub-1', 'a-owner', 'wx-1', '["task_completed"]', '["dev-1"]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'active')
            """
        )
        conn.commit()

    response = client.delete("/device/v1/app/notifications/subscriptions/sub-1", headers=_headers("a-other"))
    assert response.status_code == 404, response.text

    with connect() as conn:
        row = conn.execute("SELECT status FROM v2_notification_subscription WHERE id='sub-1'").fetchone()
    assert row["status"] == "active"


def test_subscribe_rejects_empty_device_ids(client):
    _seed_account_and_device()
    _seed_binding()
    with connect() as conn:
        conn.execute("UPDATE v2_account SET wechat_openid='wx-openid-1' WHERE id='a-owner'")
        conn.commit()
    response = client.post(
        "/device/v1/app/notifications/subscribe",
        headers=_headers("a-owner"),
        json={"openid": "wx-openid-1", "templateIds": ["task_completed"]},
    )
    assert response.status_code == 400
    assert "deviceIds" in response.json()["message"]


def test_subscribe_rejects_mismatched_openid(client):
    _seed_account_and_device()
    _seed_binding()
    with connect() as conn:
        conn.execute("UPDATE v2_account SET wechat_openid='wx-real-openid' WHERE id='a-owner'")
        conn.commit()

    response = client.post(
        "/device/v1/app/notifications/subscribe",
        headers=_headers("a-owner"),
        json={
            "openid": "wx-other-openid",
            "templateIds": ["task_completed"],
            "deviceIds": ["dev-1"],
        },
    )
    assert response.status_code == 403, response.text


def test_subscribe_rejects_unauthorized_device(client):
    _seed_account_and_device()
    _seed_binding()
    with connect() as conn:
        conn.execute("UPDATE v2_account SET wechat_openid='wx-openid-1' WHERE id='a-owner'")
        conn.commit()
    response = client.post(
        "/device/v1/app/notifications/subscribe",
        headers=_headers("a-owner"),
        json={"openid": "wx-openid-1", "templateIds": ["task_completed"], "deviceIds": ["dev-other"]},
    )
    assert response.status_code == 403
