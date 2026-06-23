import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt
from device_logic.db import _schema_ready_paths, connect

def token(account_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(account_id)}"}


def seed_account_and_device(device_id: str = "dev-1", device_sn: str = "SN-APP-01") -> None:
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-other', '13002', 'other')")
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver)
            VALUES (?, ?, 'esp32s3_xyz', '1.0.0', 'rev-a')
            """,
            (device_id, device_sn),
        )
        conn.commit()


def seed_binding(
    device_id: str = "dev-1",
    account_id: str = "a-owner",
    bind_mode: str = "owner",
    binding_id: str = "b-1",
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (binding_id, device_id, account_id, bind_mode),
        )
        conn.commit()


def client(tmp_path, monkeypatch) -> tuple[TestClient, InMemoryDeviceTaskStore]:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    store = install_task_store_for_tests(InMemoryDeviceTaskStore())

    from routes.device_app_api import router as app_router
    from routes.device_app_auth import router as auth_router
    from routes.device_app_chat import router as chat_router
    from routes.device_app_members import router as member_router
    from routes.device_app_misc import router as misc_router
    from routes.device_app_tasks import router as task_router

    app = FastAPI()
    app.include_router(app_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(member_router)
    app.include_router(misc_router)
    app.include_router(task_router)
    return TestClient(app), store