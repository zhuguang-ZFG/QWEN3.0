import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.xiaozhi_v1_compat as compat
from device_logic.activation import reset_activation_store_for_tests


def _token(account_id: str) -> str:
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return compat.jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def _headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(account_id)}"}


def _seed_base() -> None:
    with compat._connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '10001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-target', '10002', 'target')")
        conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-1', 'SN-001', 'esp32s3_xyz')")
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES ('b-owner', 'd-1', 'a-owner', 'owner', 'active')
            """
        )
        conn.execute(
            "INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-owner', 'd-1', 'child')"
        )
        conn.execute(
            "INSERT INTO v2_voiceprint (id, member_id, device_id, status) VALUES ('vp-1', 'm-1', 'd-1', 'enrolled')"
        )
        conn.execute("UPDATE v2_member SET voiceprint_id='vp-1' WHERE id='m-1'")
        conn.commit()


def _json(response):
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == 0
    return data["data"]


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "xiaozhi.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    compat._schema_ready_paths.clear()
    reset_activation_store_for_tests()
    app = FastAPI()
    app.include_router(compat.router)
    _seed_base()
    return TestClient(app)


def test_device_register_bind_unbind_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    owner = _json(client.post("/api/v1/auth/register", json={"phone": "13003", "code": "000000"}))
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    with compat._connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, hardware_ver, firmware_ver)
            VALUES ('pd-01', 'SN-P0-01', 'esp32s3_xyz', 'v1', '0.9.0')
            """
        )
        conn.commit()

    registered = _json(
        client.post(
            "/api/v1/devices/register",
            headers=owner_headers,
            json={"model": "esp32s3_xyz", "hardwareVer": "v1", "firmwareVer": "0.9.0"},
        )
    )
    activation_code = registered["activationCode"]
    assert len(activation_code) == 6
    assert activation_code.isdigit()

    bound = _json(
        client.post(
            "/api/v1/devices/bind",
            headers=owner_headers,
            json={"activationCode": activation_code, "deviceSn": "SN-P0-01", "nickname": "my-bot"},
        )
    )
    assert bound["deviceId"] == "pd-01"
    assert bound["device"]["model"] == "esp32s3_xyz"
    assert bound["device"]["deviceSn"] == "SN-P0-01"

    devices = _json(client.get("/api/v1/devices", headers=owner_headers))
    assert any(device["deviceId"] == "pd-01" for device in devices)

    unbound = _json(client.post("/api/v1/devices/pd-01/unbind", headers=owner_headers))
    assert unbound == {"deviceId": "pd-01", "status": "unbound"}

    with compat._connect() as conn:
        binding = conn.execute("SELECT * FROM v2_device_binding WHERE device_id='pd-01'").fetchone()
    assert binding is not None
    assert binding["status"] == "unbound"


def test_device_detail_and_update(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    owner = _json(client.post("/api/v1/auth/register", json={"phone": "13004", "code": "000000"}))
    headers = {"Authorization": f"Bearer {owner['token']}"}
    with compat._connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, hardware_ver, firmware_ver)
            VALUES ('pd-02', 'SN-P0-02', 'esp32s3_xyz', 'v1', '0.9.0')
            """
        )
        conn.commit()
    activation = _json(client.post("/api/v1/devices/register", headers=headers, json={"model": "esp32s3_xyz"}))
    bound = _json(
        client.post(
            "/api/v1/devices/bind",
            headers=headers,
            json={"activationCode": activation["activationCode"], "deviceSn": "SN-P0-02"},
        )
    )
    device_id = bound["deviceId"]

    detail = _json(client.get(f"/api/v1/devices/{device_id}", headers=headers))
    assert detail["model"] == "esp32s3_xyz"
    assert detail["deviceSn"] == "SN-P0-02"
    assert detail["status"] == "offline"

    updated = _json(
        client.put(
            f"/api/v1/devices/{device_id}",
            headers=headers,
            json={"model": "new_model", "firmwareVer": "2.0"},
        )
    )
    assert updated["model"] == "new_model"
    assert updated["firmwareVer"] == "2.0"

    with compat._connect() as conn:
        row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    assert row["model"] == "new_model"
    assert row["firmware_ver"] == "2.0"


def test_device_activation_code_expiry(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_ACTIVATION_CODE", "strict")

    registered = _json(
        client.post(
            "/api/v1/devices/register",
            headers=_headers("a-owner"),
            json={"model": "esp32s3_xyz"},
        )
    )
    assert len(registered["activationCode"]) == 6

    response = client.post(
        "/api/v1/devices/bind",
        headers=_headers("a-owner"),
        json={"activationCode": "badbad", "deviceSn": "SN-P0-BAD"},
    )
    assert response.status_code >= 400
    assert response.json()["code"] != 0

    with compat._connect() as conn:
        binding = conn.execute(
            """
            SELECT b.*
            FROM v2_device_binding b
            JOIN v2_device d ON d.id = b.device_id
            WHERE d.device_sn='SN-P0-BAD'
            """
        ).fetchone()
    assert binding is None
