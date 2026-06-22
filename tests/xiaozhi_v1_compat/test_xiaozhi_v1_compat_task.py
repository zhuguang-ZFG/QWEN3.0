from .helpers import _client, _headers, _json, _seed_base, _token


import routes.xiaozhi_v1_compat as compat


def _register_and_bind_device(client, phone: str, device_id: str, device_sn: str, monkeypatch):
    """Register user, create device, activate and bind. Returns (headers, device_id)."""
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    owner = _json(client.post("/api/v1/auth/register", json={"phone": phone, "code": "000000"}))
    hdrs = {"Authorization": f"Bearer {owner['token']}"}
    with compat._connect() as conn:
        conn.execute(
            "INSERT INTO v2_device (id, device_sn, model) VALUES (?, ?, 'esp32s3_xyz')",
            (device_id, device_sn),
        )
        conn.commit()
    activation = _json(client.post("/api/v1/devices/register", headers=hdrs, json={"model": "esp32s3_xyz"}))
    bound = _json(
        client.post(
            "/api/v1/devices/bind",
            headers=hdrs,
            json={"activationCode": activation["activationCode"], "deviceSn": device_sn},
        )
    )
    return hdrs, bound["deviceId"]


def _create_approval_task(client, hdrs: dict, device_id: str, path: list) -> dict:
    """Create a task with requireApproval=True."""
    return _json(
        client.post(
            f"/api/v1/devices/{device_id}/tasks",
            headers=hdrs,
            json={"capability": "run_path", "source": "voice", "params": {"path": path, "requireApproval": True}},
        )
    )


def test_task_create_list_detail_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    owner = _json(client.post("/api/v1/auth/register", json={"phone": "13005", "code": "000000"}))
    headers = {"Authorization": f"Bearer {owner['token']}"}
    with compat._connect() as conn:
        conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('pd-03', 'SN-P0-03', 'esp32s3_xyz')")
        conn.commit()
    activation = _json(client.post("/api/v1/devices/register", headers=headers, json={"model": "esp32s3_xyz"}))
    bound = _json(
        client.post(
            "/api/v1/devices/bind",
            headers=headers,
            json={"activationCode": activation["activationCode"], "deviceSn": "SN-P0-03"},
        )
    )
    path = [{"x": 0, "y": 0, "z": 0}, {"x": 5, "y": 5, "z": 0}]
    task = _json(
        client.post(
            f"/api/v1/devices/{bound['deviceId']}/tasks",
            headers=headers,
            json={"capability": "run_path", "source": "voice", "params": {"path": path, "requireApproval": True}},
        )
    )
    assert task["taskId"]
    assert task["status"] == "pending"

    tasks = _json(client.get(f"/api/v1/devices/{bound['deviceId']}/tasks", headers=headers))
    assert any(row["taskId"] == task["taskId"] for row in tasks)

    detail = _json(client.get(f"/api/v1/tasks/{task['taskId']}", headers=headers))
    assert detail["taskId"] == task["taskId"]
    assert detail["capability"] == "run_path"
    assert detail["status"] == "pending"

    with compat._connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task["taskId"],)).fetchone()
    assert row is not None
    assert row["device_id"] == "pd-03"
    assert row["status"] == "pending"


def test_task_approve_reject_pending_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    hdrs, device_id = _register_and_bind_device(client, "13006", "pd-04", "SN-P0-04", monkeypatch)
    path = [{"x": 0, "y": 0, "z": 0}, {"x": 3, "y": 3, "z": 0}]

    first = _create_approval_task(client, hdrs, device_id, path)
    pending = _json(client.get(f"/api/v1/devices/{device_id}/tasks/pending", headers=hdrs))
    assert any(row["taskId"] == first["taskId"] for row in pending)

    approved = _json(client.post(f"/api/v1/tasks/{first['taskId']}/approve", headers=hdrs))
    assert approved["status"] == "approved"

    second = _create_approval_task(client, hdrs, device_id, path)
    rejected = _json(
        client.post(f"/api/v1/tasks/{second['taskId']}/reject", headers=hdrs, json={"reason": "not now"})
    )
    assert rejected["status"] == "rejected"

    third = _create_approval_task(client, hdrs, device_id, path)
    pending = _json(client.get(f"/api/v1/devices/{device_id}/tasks/pending", headers=hdrs))
    assert third["taskId"] in {row["taskId"] for row in pending}

    with compat._connect() as conn:
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM v2_task WHERE device_id='pd-04'").fetchall()
        }
    assert statuses[first["taskId"]] == "approved"
    assert statuses[second["taskId"]] == "rejected"
    assert statuses[third["taskId"]] == "pending"
