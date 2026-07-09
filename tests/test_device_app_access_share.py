"""Tests for unified device access checks (share expiry)."""

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_app_sharing_helpers import seed_guest
from device_logic.db import connect


def _expire_share() -> None:
    with connect() as conn:
        conn.execute("UPDATE v2_device_share SET expires_at='2020-01-01T00:00:00Z' WHERE device_id='dev-1'")
        conn.commit()


def test_expired_share_cannot_read_tasks(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    accept = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accept.status_code == 200

    _expire_share()

    response = client.get("/device/v1/app/tasks?device_id=dev-1", headers=headers("a-guest"))
    assert response.status_code == 403


def test_view_share_cannot_create_member(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    response = client.post(
        "/device/v1/app/members",
        headers=headers("a-guest"),
        json={"deviceId": "dev-1", "name": "kid", "role": "child"},
    )
    assert response.status_code == 403
