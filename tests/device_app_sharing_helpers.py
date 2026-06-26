"""Shared helpers/fixtures for device app sharing tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_app_helpers import token as make_token
from device_gateway.sessions import registry
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.db import _schema_ready_paths, connect


def _sharing_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())

    from routes.device_app_api import router as app_router
    from routes.device_app_assets import router as assets_router
    from routes.device_app_sharing import router as sharing_router
    from routes.device_app_task_extras import router as task_extras_router
    from routes.device_app_task_templates import router as template_router
    from routes.device_app_tasks import router as task_router

    registry.clear()
    app = FastAPI()
    app.include_router(app_router)
    app.include_router(sharing_router)
    app.include_router(task_router)
    app.include_router(task_extras_router)
    app.include_router(template_router)
    app.include_router(assets_router)
    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    return _sharing_client(tmp_path, monkeypatch)


def seed_guest() -> None:
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-guest', '13003', 'guest')")
        conn.commit()


def seed_guest_token(account_id: str = "a-guest") -> str:
    return make_token(account_id)


def accept_share(client, permission: str = "view") -> None:
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": permission},
    )
    assert create.status_code == 200
    token = create.json()["shareToken"]
    accept = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accept.status_code == 200
