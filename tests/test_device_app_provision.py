"""Tests for device discovery and retired insecure pre-binding routes."""

from device_app_helpers import client as make_client
from device_app_helpers import headers
from device_logic.db import connect


def _provision_client(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    from routes.device_app_provision import router as provision_router

    client.app.include_router(provision_router)
    return client, store


def _seed_account():
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.commit()


def test_discover_with_client_reported_devices(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()
    response = client.post(
        "/device/v1/app/devices/discover",
        headers=headers("a-owner"),
        json={
            "devices": [
                {"deviceSn": "SN-01", "model": "esp32s3", "firmwareVer": "1.0.0", "ip": "192.168.1.10"},
                {"deviceSn": "SN-02", "model": "esp32c3"},
                {"invalid": "no serial"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert [item["deviceSn"] for item in response.json()["devices"]] == ["SN-01", "SN-02"]


def test_provision_requires_auth_before_retired_response(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    assert client.post("/device/v1/app/devices/provision").status_code == 401


def test_provision_is_retired_to_prevent_unbound_sn_claim(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()
    response = client.post(
        "/device/v1/app/devices/provision",
        headers=headers("a-owner"),
        json={"deviceSn": "SN-UNBOUND", "wifiSsid": "MyWiFi"},
    )
    assert response.status_code == 410
    assert "activation-code binding" in response.json()["message"]


def test_provision_confirm_is_retired_even_with_self_issued_token(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    response = client.post(
        "/device/v1/app/devices/provision/confirm",
        json={"provisionToken": "attacker-created-token", "deviceSn": "SN-UNBOUND"},
    )
    assert response.status_code == 410
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM v2_device WHERE device_sn='SN-UNBOUND'").fetchone() is None
