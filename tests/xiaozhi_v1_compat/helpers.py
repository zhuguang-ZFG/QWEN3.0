"""[DEPRECATED v3.1] Tests for retired XiaoZhi v1 compatibility layer.
Kept for reference only; do not extend."""


import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.xiaozhi_v1_compat as compat

def _token(account_id: str, role: str = "user") -> str:
    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": role,
        "iat": now,
        "exp": now + 3600,
    }
    return compat.jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def _headers(account_id: str, role: str = "user") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(account_id, role)}"}


def _seed_base() -> None:
    """Insert the standard base dataset used by most xiaozhi compat tests."""
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


def _client(tmp_path, monkeypatch, seed_base=None) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "xiaozhi.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    compat._schema_ready_paths.clear()
    app = FastAPI()
    app.include_router(compat.router)
    (seed_base or _seed_base)()
    return TestClient(app)