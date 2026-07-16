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
from device_logic.notifications import WeChatNotifier, dispatch_notification, notifier


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


@pytest.mark.asyncio
async def test_dispatch_notification_uses_mock_notifier_and_writes_log(client, monkeypatch, tmp_path):
    _seed_account_and_device()
    _seed_binding()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_notification_subscription
            (id, account_id, openid, template_ids, device_ids, created_at, updated_at, status)
            VALUES ('sub-2', 'a-owner', 'wx-2', '["task_completed"]', '["dev-1"]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'active')
            """
        )
        conn.commit()

    sent_messages = []

    async def fake_send(openid, template_key, data, page=""):
        sent_messages.append({"openid": openid, "template_key": template_key, "data": data, "page": page})
        return {"status": "sent", "wx_response": {"errcode": 0}}

    monkeypatch.setattr(notifier, "send_subscribe_message", fake_send)

    await dispatch_notification(
        "dev-1",
        "task_completed",
        {"task_name": "test-task", "task_id": "t-1", "completed_at": "2026-01-01T00:00:00Z"},
    )

    assert len(sent_messages) == 1
    assert sent_messages[0]["openid"] == "wx-2"
    assert sent_messages[0]["template_key"] == "task_completed"

    with connect() as conn:
        log = conn.execute("SELECT * FROM v2_notification_log WHERE account_id='a-owner'").fetchone()
    assert log is not None
    assert log["event_type"] == "task_completed"
    assert log["status"] == "sent"
    assert "t-1" in log["payload"]


@pytest.mark.asyncio
async def test_dispatch_notification_filters_by_device_and_event(client, monkeypatch):
    _seed_account_and_device()
    _seed_binding()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_notification_subscription
            (id, account_id, openid, template_ids, device_ids, created_at, updated_at, status)
            VALUES ('sub-dev1', 'a-owner', 'wx-1', '["task_completed"]', '["dev-1"]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO v2_notification_subscription
            (id, account_id, openid, template_ids, device_ids, created_at, updated_at, status)
            VALUES ('sub-other', 'a-owner', 'wx-2', '["task_failed"]', '["dev-1"]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO v2_notification_subscription
            (id, account_id, openid, template_ids, device_ids, created_at, updated_at, status)
            VALUES ('sub-other-device', 'a-owner', 'wx-3', '["task_completed"]', '["dev-2"]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'active')
            """
        )
        conn.commit()

    sent_messages = []

    async def fake_send(openid, template_key, data, page=""):
        sent_messages.append(openid)
        return {"status": "sent", "wx_response": {"errcode": 0}}

    monkeypatch.setattr(notifier, "send_subscribe_message", fake_send)

    await dispatch_notification(
        "dev-1",
        "task_completed",
        {"task_name": "test-task", "task_id": "t-1", "completed_at": "2026-01-01T00:00:00Z"},
    )

    assert sent_messages == ["wx-1"]


@pytest.mark.asyncio
async def test_wechat_notifier_returns_failed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LIMA_WX_APPID", raising=False)
    monkeypatch.delenv("LIMA_WX_SECRET", raising=False)
    n = WeChatNotifier()
    result = await n.send_subscribe_message(
        "wx-openid",
        "task_completed",
        {"task_name": "task", "task_id": "t-1", "completed_at": "2026-01-01T00:00:00Z"},
    )
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_revoked_share_subscription_is_not_dispatched(client, monkeypatch):
    _seed_account_and_device()
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_device_share "
            "(id, device_id, owner_account_id, guest_account_id, share_token, permission, status, expires_at, created_at) "
            "VALUES ('s-1', 'dev-1', 'a-owner', 'a-other', 'token', 'view', 'revoked', "
            "'2099-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) "
            "VALUES ('b-shared', 'dev-1', 'a-other', 'shared', 'active')"
        )
        conn.execute(
            "INSERT INTO v2_notification_subscription "
            "(id, account_id, openid, template_ids, device_ids, created_at, updated_at, status) "
            "VALUES ('sub-revoked', 'a-other', 'wx-other', '[\"task_completed\"]', '[\"dev-1\"]', "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'active')"
        )
        conn.commit()
    sent = []

    async def fake_send(**kwargs):
        sent.append(kwargs)
        return {"status": "sent", "wx_response": {"errcode": 0}}

    monkeypatch.setattr(notifier, "send_subscribe_message", fake_send)
    await dispatch_notification("dev-1", "task_completed", {"task_name": "private"})
    assert sent == []
