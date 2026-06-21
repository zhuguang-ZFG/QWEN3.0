"""P2 tests for XiaoZhi v1 compatibility layer: captcha, change-password, manual-add, OpenAPI aliases."""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.xiaozhi_v1_compat as compat


def _token(account_id: str, role: str = "user") -> str:
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return compat.jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def _headers(account_id: str, role: str = "user") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(account_id, role)}"}


def _seed_base() -> None:
    with compat._connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '10001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname, role) VALUES ('a-admin', '10002', 'admin', 'admin')")
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


def test_get_captcha_returns_png_and_captcha_id(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/auth/captcha")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    captcha_id = response.headers["x-captcha-id"]
    assert captcha_id
    assert len(response.content) > 0


def test_sms_verification_with_optional_captcha(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    # Without captcha still works when not required.
    sms = _json(client.post("/api/v1/auth/sms-verification", json={"phone": "13001"}))
    assert sms["phone"] == "13001"

    # With a valid captcha also works.
    captcha_resp = client.get("/api/v1/auth/captcha")
    captcha_id = captcha_resp.headers["x-captcha-id"]
    # Peek the code from the database for the test.
    with compat._connect() as conn:
        code = conn.execute("SELECT code FROM v2_captcha WHERE id=?", (captcha_id,)).fetchone()["code"]

    sms = _json(
        client.post(
            "/api/v1/auth/sms-verification",
            json={"phone": "13002", "captchaId": captcha_id, "captcha": code},
        )
    )
    assert sms["phone"] == "13002"


def test_sms_verification_requires_captcha_when_enabled(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    monkeypatch.setenv("LIMA_XIAOZHI_CAPTCHA_REQUIRED", "1")

    response = client.post("/api/v1/auth/sms-verification", json={"phone": "13003"})
    assert response.status_code == 400
    assert response.json()["code"] != 0


def test_change_password(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    from routes.xiaozhi_compat.auth import _hash_password

    with compat._connect() as conn:
        conn.execute(
            "UPDATE v2_account SET password_hash=? WHERE id='a-owner'",
            (_hash_password("oldpass"),),
        )
        conn.commit()

    # Wrong old password.
    response = client.put(
        "/api/v1/auth/change-password",
        headers=_headers("a-owner"),
        json={"oldPassword": "wrong", "newPassword": "newpass"},
    )
    assert response.status_code == 400
    assert response.json()["code"] != 0

    # Correct change.
    data = _json(
        client.put(
            "/api/v1/auth/change-password",
            headers=_headers("a-owner"),
            json={"oldPassword": "oldpass", "newPassword": "newpass"},
        )
    )
    assert data["accountId"] == "a-owner"

    with compat._connect() as conn:
        row = conn.execute("SELECT password_hash FROM v2_account WHERE id='a-owner'").fetchone()
    from routes.xiaozhi_compat.auth import _verify_password

    assert _verify_password("newpass", row["password_hash"])


def test_change_password_rejected_when_no_password_set(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.put(
        "/api/v1/auth/change-password",
        headers=_headers("a-owner"),
        json={"oldPassword": "oldpass", "newPassword": "newpass"},
    )
    assert response.status_code == 400
    assert response.json()["code"] != 0


def test_manual_add_device_admin_only(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    # Non-admin is rejected.
    response = client.post(
        "/api/v1/devices/manual-add",
        headers=_headers("a-owner"),
        json={"deviceSn": "SN-MANUAL-001", "model": "esp32s3_xyz"},
    )
    assert response.status_code == 403

    # Admin succeeds.
    data = _json(
        client.post(
            "/api/v1/devices/manual-add",
            headers=_headers("a-admin", role="admin"),
            json={"deviceSn": "SN-MANUAL-001", "model": "esp32s3_xyz"},
        )
    )
    assert data["deviceSn"] == "SN-MANUAL-001"
    assert data["model"] == "esp32s3_xyz"

    # Duplicate serial number is rejected.
    response = client.post(
        "/api/v1/devices/manual-add",
        headers=_headers("a-admin", role="admin"),
        json={"deviceSn": "SN-MANUAL-001"},
    )
    assert response.status_code == 409


def test_auth_login_alias(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    data = _json(client.post("/api/v1/auth/login", json={"phone": "13004", "code": "000000"}))
    assert data["token"]
    assert data["phone"] == "13004"


def test_create_member_via_device_path_alias(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    data = _json(
        client.post(
            "/api/v1/devices/d-1/members",
            headers=_headers("a-owner"),
            json={"name": "parent", "role": "parent"},
        )
    )
    assert data["name"] == "parent"
    assert data["role"] == "parent"
    assert data["deviceId"] == "d-1"


def test_enroll_voiceprint_via_openapi_path_alias(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    data = _json(
        client.post(
            "/api/v1/voiceprints/any-id",
            headers=_headers("a-owner"),
            json={"memberId": "m-1", "deviceId": "d-1"},
        )
    )
    assert data["memberId"] == "m-1"
    assert data["deviceId"] == "d-1"


def test_cancel_transfer_put_alias(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    transfer = _json(
        client.post(
            "/api/v1/devices/d-1/transfer",
            headers=_headers("a-owner"),
            json={"toAccountId": "a-admin"},
        )
    )
    cancelled = _json(client.put(f"/api/v1/transfers/{transfer['id']}/cancel", headers=_headers("a-owner")))
    assert cancelled["status"] == "cancelled"


def test_hash_password_requires_bcrypt(monkeypatch):
    import device_logic.auth as auth_mod

    monkeypatch.setattr(auth_mod, "bcrypt", None)
    monkeypatch.setattr(auth_mod, "_BCRYPT_IMPORT_ERROR", ImportError("no bcrypt"))

    try:
        auth_mod._hash_password("secret")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "bcrypt is required" in str(exc)
