"""Tests for device app provision and discover routes."""

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
    data = response.json()
    assert data["source"] == "client_report"
    devices = data["devices"]
    assert len(devices) == 2
    assert devices[0]["deviceSn"] == "SN-01"


def test_provision_returns_token(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()

    response = client.post(
        "/device/v1/app/devices/provision",
        headers=headers("a-owner"),
        json={"deviceSn": "SN-PAIR-01", "wifiSsid": "MyWiFi", "wifiPassword": "secret"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deviceSn"] == "SN-PAIR-01"
    assert data["provisionToken"]
    assert data["serverUrl"] == "wss://chat.donglicao.com/device/v1/ws"
    assert data["configPayload"]["wifi_ssid"] == "MyWiFi"
    assert "wifi_password" not in data["configPayload"]
    assert "secret" not in response.text
    assert data["configPayload"]["pair_token"] == data["provisionToken"]
    assert data["configPayload"]["server_url"] == data["serverUrl"]


def test_provision_server_url_ignores_host_header(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()
    monkeypatch.delenv("LIMA_DEVICE_WS_URL", raising=False)

    response = client.post(
        "/device/v1/app/devices/provision",
        headers={**headers("a-owner"), "Host": "evil.example.com"},
        json={"deviceSn": "SN-PAIR-HOST", "wifiSsid": "MyWiFi", "wifiPassword": "secret"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["serverUrl"] == "wss://chat.donglicao.com/device/v1/ws"
    assert "evil.example.com" not in data["serverUrl"]


def test_provision_server_url_from_env(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()
    monkeypatch.setenv("LIMA_DEVICE_WS_URL", "wss://custom.example.com/device/v1/ws")

    response = client.post(
        "/device/v1/app/devices/provision",
        headers=headers("a-owner"),
        json={"deviceSn": "SN-PAIR-ENV", "wifiSsid": "MyWiFi", "wifiPassword": "secret"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["serverUrl"] == "wss://custom.example.com/device/v1/ws"


def test_confirm_provision_binds_device(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()

    pair_response = client.post(
        "/device/v1/app/devices/provision",
        headers=headers("a-owner"),
        json={"deviceSn": "SN-PAIR-02", "wifiSsid": "MyWiFi"},
    )
    assert pair_response.status_code == 200, pair_response.text
    provision_token = pair_response.json()["provisionToken"]

    confirm_response = client.post(
        "/device/v1/app/devices/provision/confirm",
        json={"provisionToken": provision_token, "deviceSn": "SN-PAIR-02"},
    )

    assert confirm_response.status_code == 200, confirm_response.text
    data = confirm_response.json()
    assert data["status"] == "bound"
    assert data["deviceSn"] == "SN-PAIR-02"
    assert data["accountId"] == "a-owner"


def test_confirm_invalid_provision_token_returns_404(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()

    response = client.post(
        "/device/v1/app/devices/provision/confirm",
        json={"provisionToken": "invalid-token", "deviceSn": "SN-PAIR-03"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_confirm_expired_provision_token_returns_400(tmp_path, monkeypatch):
    client, _store = _provision_client(tmp_path, monkeypatch)
    _seed_account()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_pair_request
            (id, pair_token, device_sn, account_id, wifi_ssid, server_url, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pair-expired",
                "expired-token-12345",
                "SN-PAIR-04",
                "a-owner",
                "WiFi",
                "wss://example.com/device/v1/ws",
                "2020-01-01T00:00:00Z",
            ),
        )
        conn.commit()

    response = client.post(
        "/device/v1/app/devices/provision/confirm",
        json={"provisionToken": "expired-token-12345", "deviceSn": "SN-PAIR-04"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400
