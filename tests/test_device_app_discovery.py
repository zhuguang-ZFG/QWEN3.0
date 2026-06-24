"""Tests for device app discovery and pairing routes."""

from device_app_helpers import client as make_client
from device_app_helpers import headers
from device_logic.db import connect


def _discovery_client(tmp_path, monkeypatch):
    """Create a test client with the discovery router mounted."""
    client, store = make_client(tmp_path, monkeypatch)
    from routes.device_app_discovery import router as discovery_router

    client.app.include_router(discovery_router)
    return client, store


def _seed_account():
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.commit()


def test_discover_with_client_reported_devices(tmp_path, monkeypatch):
    client, _store = _discovery_client(tmp_path, monkeypatch)
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
    assert devices[0]["model"] == "esp32s3"
    assert devices[0]["firmwareVer"] == "1.0.0"
    assert devices[0]["ip"] == "192.168.1.10"
    assert devices[1]["deviceSn"] == "SN-02"


def test_pair_returns_token(tmp_path, monkeypatch):
    client, _store = _discovery_client(tmp_path, monkeypatch)
    _seed_account()

    response = client.post(
        "/device/v1/app/devices/pair",
        headers=headers("a-owner"),
        json={"deviceSn": "SN-PAIR-01", "wifiSsid": "MyWiFi", "wifiPassword": "secret"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deviceSn"] == "SN-PAIR-01"
    assert data["pairToken"]
    assert data["serverUrl"]
    assert data["configPayload"]["wifi_ssid"] == "MyWiFi"
    assert data["configPayload"]["wifi_password"] == "secret"
    assert data["configPayload"]["pair_token"] == data["pairToken"]
    assert data["configPayload"]["device_sn"] == "SN-PAIR-01"


def test_confirm_binds_device(tmp_path, monkeypatch):
    client, _store = _discovery_client(tmp_path, monkeypatch)
    _seed_account()

    pair_response = client.post(
        "/device/v1/app/devices/pair",
        headers=headers("a-owner"),
        json={"deviceSn": "SN-PAIR-02", "wifiSsid": "MyWiFi"},
    )
    assert pair_response.status_code == 200, pair_response.text
    pair_token = pair_response.json()["pairToken"]

    confirm_response = client.post(
        "/device/v1/app/devices/pair/confirm",
        json={"pairToken": pair_token, "deviceSn": "SN-PAIR-02"},
    )

    assert confirm_response.status_code == 200, confirm_response.text
    data = confirm_response.json()
    assert data["status"] == "bound"
    assert data["deviceSn"] == "SN-PAIR-02"
    assert data["accountId"] == "a-owner"

    with connect() as conn:
        binding = conn.execute(
            """
            SELECT * FROM v2_device_binding
            WHERE device_id=(SELECT id FROM v2_device WHERE device_sn=?)
              AND account_id=?
            """,
            ("SN-PAIR-02", "a-owner"),
        ).fetchone()
        assert binding is not None
        assert binding["status"] == "active"
        assert binding["bind_mode"] == "owner"


def test_confirm_invalid_token_returns_404(tmp_path, monkeypatch):
    client, _store = _discovery_client(tmp_path, monkeypatch)
    _seed_account()

    response = client.post(
        "/device/v1/app/devices/pair/confirm",
        json={"pairToken": "invalid-token", "deviceSn": "SN-PAIR-03"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_confirm_expired_token_returns_400(tmp_path, monkeypatch):
    client, _store = _discovery_client(tmp_path, monkeypatch)
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
        "/device/v1/app/devices/pair/confirm",
        json={"pairToken": "expired-token-12345", "deviceSn": "SN-PAIR-04"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400
