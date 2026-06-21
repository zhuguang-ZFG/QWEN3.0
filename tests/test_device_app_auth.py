from device_logic.db import connect
from device_app_helpers import client as make_client
from device_app_helpers import seed_account_and_device


def test_device_app_auth_rejects_static_code_without_dev_mode(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    monkeypatch.delenv("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", raising=False)

    response = client.post(
        "/device/v1/app/auth/register",
        json={"phone": "13900", "code": "000000", "nickname": "native-owner"},
    )

    assert response.status_code == 503


def test_device_app_auth_register_login_sms_me_and_delete_flow(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    monkeypatch.setenv("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", "1")

    registered = client.post(
        "/device/v1/app/auth/register",
        json={"phone": "13901", "code": "000000", "nickname": "native-owner"},
    )
    assert registered.status_code == 200, registered.text
    register_data = registered.json()
    assert register_data["accountId"]
    assert register_data["token"]

    logged_in = client.post("/device/v1/app/auth/login", json={"phone": "13901", "code": "000000"})
    assert logged_in.status_code == 200, logged_in.text
    login_data = logged_in.json()
    assert login_data["accountId"] == register_data["accountId"]

    sms = client.post("/device/v1/app/auth/sms-verification", json={"phone": "13901"})
    assert sms.status_code == 200, sms.text
    assert sms.json() == {"phone": "13901", "mock": True, "expiresIn": 300}

    me = client.get("/device/v1/app/auth/me", headers={"Authorization": f"Bearer {login_data['token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["nickname"] == "native-owner"

    seed_account_and_device(device_id="d-auth", device_sn="SN-AUTH-01")
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES ('b-auth', 'd-auth', ?, 'owner', 'active')",
            (register_data["accountId"],),
        )
        conn.commit()

    deleted = client.post(
        "/device/v1/app/auth/account/delete", headers={"Authorization": f"Bearer {login_data['token']}"}
    )
    assert deleted.status_code == 200, deleted.text
    with connect() as conn:
        account = conn.execute("SELECT * FROM v2_account WHERE id=?", (register_data["accountId"],)).fetchone()
        binding = conn.execute("SELECT * FROM v2_device_binding WHERE id='b-auth'").fetchone()
    assert account["status"] == "deleted"
    assert binding["status"] == "unbound"


def test_device_app_auth_fails_closed_without_configured_login_code(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.delenv("LIMA_XIAOZHI_LOGIN_CODE", raising=False)

    sms = client.post("/device/v1/app/auth/sms-verification", json={"phone": "13902"})
    assert sms.status_code == 503

    registered = client.post(
        "/device/v1/app/auth/register",
        json={"phone": "13902", "code": "000000", "nickname": "native-owner"},
    )
    assert registered.status_code == 503

    logged_in = client.post("/device/v1/app/auth/login", json={"phone": "13902", "code": "000000"})
    assert logged_in.status_code == 503


def test_device_app_auth_rejects_wechat_code_login_without_dev_flag(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.delenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", raising=False)

    logged_in = client.post("/device/v1/app/auth/login", json={"code": "wx-code-1"})
    assert logged_in.status_code == 503


def test_device_app_auth_dev_mode_without_login_code_returns_503(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", "1")
    monkeypatch.delenv("LIMA_XIAOZHI_LOGIN_CODE", raising=False)

    endpoints = [
        ("/device/v1/app/auth/sms-verification", {"phone": "13903"}),
        ("/device/v1/app/auth/register", {"phone": "13903", "code": "000000", "nickname": "native-owner"}),
        ("/device/v1/app/auth/login", {"phone": "13903", "code": "000000"}),
    ]
    for path, body in endpoints:
        response = client.post(path, json=body)
        assert response.status_code == 503, f"{path}: {response.text}"
        assert "SMS verification code is not configured" in response.json()["message"]
