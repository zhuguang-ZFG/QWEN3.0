from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


def test_device_app_bind_list_unbind_flow(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()

    registered = client.post(
        "/device/v1/app/devices/register",
        headers=headers("a-owner"),
        json={"model": "esp32s3_xyz", "hardwareVer": "rev-a", "firmwareVer": "1.0.0"},
    )
    assert registered.status_code == 200, registered.text
    activation_code = registered.json()["activationCode"]
    assert len(activation_code) == 6

    bound = client.post(
        "/device/v1/app/devices/bind",
        headers=headers("a-owner"),
        json={"activationCode": activation_code, "deviceSn": "SN-APP-01"},
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["deviceId"] == "dev-1"
    assert bound.json()["device"]["deviceSn"] == "SN-APP-01"

    devices = client.get("/device/v1/app/devices", headers=headers("a-owner"))
    assert devices.status_code == 200, devices.text
    data = devices.json()
    assert data["count"] == 1
    assert data["devices"][0]["deviceId"] == "dev-1"

    unbound = client.post("/device/v1/app/devices/dev-1/unbind", headers=headers("a-owner"))
    assert unbound.status_code == 200, unbound.text
    assert unbound.json() == {"deviceId": "dev-1", "status": "unbound"}

    devices_after = client.get("/device/v1/app/devices", headers=headers("a-owner"))
    assert devices_after.status_code == 200, devices_after.text
    assert devices_after.json() == {"devices": [], "count": 0}


def test_device_app_bind_rejects_unissued_activation_code(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.delenv("LIMA_XIAOZHI_ACTIVATION_CODE", raising=False)
    seed_account_and_device()

    response = client.post(
        "/device/v1/app/devices/bind",
        headers=headers("a-owner"),
        json={"activationCode": "not-issued", "deviceSn": "SN-APP-01"},
    )

    assert response.status_code == 401


def test_device_app_detail_and_update_flow(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    detail = client.get("/device/v1/app/devices/dev-1", headers=headers("a-owner"))
    assert detail.status_code == 200, detail.text
    assert detail.json()["deviceId"] == "dev-1"
    assert detail.json()["firmwareVer"] == "1.0.0"

    updated = client.put(
        "/device/v1/app/devices/dev-1",
        headers=headers("a-owner"),
        json={"model": "esp32c3_mini", "firmwareVer": "2.0.0", "metadata": {"workArea": "A5"}},
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["model"] == "esp32c3_mini"
    assert payload["firmwareVer"] == "2.0.0"
    assert '"workArea": "A5"' in payload["metadata"]
