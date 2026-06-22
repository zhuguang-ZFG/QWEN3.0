from .helpers import _client, _headers, _json, _seed_base, _token


import routes.xiaozhi_v1_compat as compat


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
