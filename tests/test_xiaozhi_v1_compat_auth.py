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


def test_auth_register_login_me_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    registered = _json(
        client.post(
            "/api/v1/auth/register",
            json={"phone": "13001", "code": "000000", "nickname": "p0-owner"},
        )
    )
    assert registered["accountId"]
    assert registered["token"]
    assert registered["phone"] == "13001"

    logged_in = _json(client.post("/api/v1/login", json={"phone": "13001", "code": "000000"}))
    assert logged_in["token"]
    assert logged_in["accountId"] == registered["accountId"]

    me = _json(client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {logged_in['token']}"}))
    assert me["phone"] == "13001"
    assert me["nickname"] == "p0-owner"

    with compat._connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE id=?", (registered["accountId"],)).fetchone()
    assert row is not None
    assert row["status"] == "active"
    assert row["phone"] == "13001"


def test_auth_sms_verification(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    account = _json(
        client.post(
            "/api/v1/auth/register",
            json={"phone": "13002", "code": "000000", "nickname": "sms-user"},
        )
    )
    sms = _json(client.post("/api/v1/auth/sms-verification", json={"phone": "13002"}))
    assert sms == {"phone": "13002", "mock": True, "expiresIn": 300}
    with compat._connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account["accountId"],)).fetchone()
    assert row is not None
    assert row["phone"] == "13002"
    assert row["status"] == "active"
