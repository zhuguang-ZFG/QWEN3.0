"""[DEPRECATED v3.1] Tests for retired XiaoZhi v1 compatibility layer.
Kept for reference only; do not extend."""

from .helpers import _client, _headers, _json, _seed_base, _token


import routes.xiaozhi_v1_compat as compat


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
