import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.xiaozhi_v1_compat as compat


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
    app = FastAPI()
    app.include_router(compat.router)
    _seed_base()
    return TestClient(app)


def test_unauthorized_access(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    me_response = client.get("/api/v1/auth/me")
    assert 400 <= me_response.status_code < 500

    bind_response = client.post(
        "/api/v1/devices/bind",
        json={"activationCode": "123456", "deviceSn": "SN-P0-NOAUTH"},
    )
    assert bind_response.status_code >= 400 or bind_response.json()["code"] != 0

    owner = _json(client.post("/api/v1/auth/register", json={"phone": "13007", "code": "000000"}))
    headers = {"Authorization": f"Bearer {owner['token']}"}
    with compat._connect() as conn:
        conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('pd-05', 'SN-P0-05', 'esp32s3_xyz')")
        conn.commit()
    activation = _json(client.post("/api/v1/devices/register", headers=headers, json={"model": "esp32s3_xyz"}))
    _json(
        client.post(
            "/api/v1/devices/bind",
            headers=headers,
            json={"activationCode": activation["activationCode"], "deviceSn": "SN-P0-05"},
        )
    )

    wrong_response = client.get("/api/v1/devices/pd-05/tasks", headers=_headers("a-target"))
    if wrong_response.status_code == 200:
        assert wrong_response.json()["data"] == []
    else:
        assert 400 <= wrong_response.status_code < 500

    with compat._connect() as conn:
        binding = conn.execute("SELECT * FROM v2_device_binding WHERE device_id='pd-05'").fetchone()
    assert binding is not None
    assert binding["account_id"] == owner["accountId"]
    assert binding["status"] == "active"
