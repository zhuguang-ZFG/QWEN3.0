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
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")

    owner = _json(client.post("/api/v1/auth/register", json={"phone": "13006", "code": "000000"}))
    headers = {"Authorization": f"Bearer {owner['token']}"}
    with compat._connect() as conn:
        conn.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('pd-04', 'SN-P0-04', 'esp32s3_xyz')")
        conn.commit()
    activation = _json(client.post("/api/v1/devices/register", headers=headers, json={"model": "esp32s3_xyz"}))
    bound = _json(
        client.post(
            "/api/v1/devices/bind",
            headers=headers,
            json={"activationCode": activation["activationCode"], "deviceSn": "SN-P0-04"},
        )
    )
    device_id = bound["deviceId"]
    path = [{"x": 0, "y": 0, "z": 0}, {"x": 3, "y": 3, "z": 0}]

    first = _json(
        client.post(
            f"/api/v1/devices/{device_id}/tasks",
            headers=headers,
            json={"capability": "run_path", "source": "voice", "params": {"path": path, "requireApproval": True}},
        )
    )
    pending = _json(client.get(f"/api/v1/devices/{device_id}/tasks/pending", headers=headers))
    assert any(row["taskId"] == first["taskId"] for row in pending)

    approved = _json(client.post(f"/api/v1/tasks/{first['taskId']}/approve", headers=headers))
    assert approved["status"] == "approved"

    second = _json(
        client.post(
            f"/api/v1/devices/{device_id}/tasks",
            headers=headers,
            json={"capability": "run_path", "source": "voice", "params": {"path": path, "requireApproval": True}},
        )
    )
    rejected = _json(
        client.post(f"/api/v1/tasks/{second['taskId']}/reject", headers=headers, json={"reason": "not now"})
    )
    assert rejected["status"] == "rejected"

    third = _json(
        client.post(
            f"/api/v1/devices/{device_id}/tasks",
            headers=headers,
            json={"capability": "run_path", "source": "voice", "params": {"path": path, "requireApproval": True}},
        )
    )
    pending = _json(client.get(f"/api/v1/devices/{device_id}/tasks/pending", headers=headers))
    assert third["taskId"] in {row["taskId"] for row in pending}

    with compat._connect() as conn:
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM v2_task WHERE device_id='pd-04'").fetchall()
        }
    assert statuses[first["taskId"]] == "approved"
    assert statuses[second["taskId"]] == "rejected"
    assert statuses[third["taskId"]] == "pending"
