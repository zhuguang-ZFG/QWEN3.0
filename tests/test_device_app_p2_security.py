"""Tests for app_status_ws_ticket and WS ticket auth."""

from __future__ import annotations

import app_status_ws_ticket
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


def test_ws_ticket_stores_account_id_not_jwt(tmp_path, monkeypatch):
    app_status_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_status_ws._POLL_INTERVAL", 0.05)
    monkeypatch.delenv("LIMA_DEVICE_APP_WS_QUERY_AUTH", raising=False)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    issued = client.post(
        "/device/v1/app/devices/dev-1/ws/ticket",
        headers=headers("a-owner"),
        json={},
    )
    assert issued.status_code == 200, issued.text
    ticket = issued.json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/devices/dev-1/ws?ticket={ticket}") as websocket:
        message = websocket.receive_json()
        assert message["event"] == "status_snapshot"
        assert message["payload"]["deviceId"] == "dev-1"


def test_wechat_dev_login_blocked_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", "1")
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    monkeypatch.delenv("LIMA_WX_APPID", raising=False)
    monkeypatch.delenv("LIMA_WX_SECRET", raising=False)
    client, _store = make_client(tmp_path, monkeypatch)

    response = client.post("/device/v1/app/auth/login", json={"code": "wx-prod-blocked"})
    assert response.status_code == 503
    assert "not configured" in response.json()["message"].lower()


def test_transfer_by_wechat_openid(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    with __import__("device_logic.db", fromlist=["connect"]).connect() as conn:
        conn.execute("UPDATE v2_account SET wechat_openid='o-recipient-1' WHERE id='a-other'")
        conn.commit()

    response = client.post(
        "/device/v1/app/devices/dev-1/transfer",
        headers=headers("a-owner"),
        json={"toOpenid": "o-recipient-1", "reason": "family"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["toAccountId"] == "a-other"


def test_create_asset_rejects_non_admin(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    response = client.post(
        "/device/v1/app/assets",
        headers=headers("a-owner"),
        json={
            "title": "user asset",
            "category": "starter",
            "content": "<svg></svg>",
            "difficulty": "easy",
            "tags": [],
        },
    )
    assert response.status_code == 403
