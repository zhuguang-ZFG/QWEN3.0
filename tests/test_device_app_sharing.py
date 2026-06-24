import time
from pathlib import Path

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


def test_create_share(client):
    seed_account_and_device()
    seed_binding()
    response = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deviceId"] == "dev-1"
    assert data["permission"] == "view"
    assert data["status"] == "pending"
    assert data["shareToken"]
    assert data["expiresAt"]


def test_list_shares(client):
    seed_account_and_device()
    seed_binding()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "control"},
    )
    assert create.status_code == 200

    response = client.get("/device/v1/app/devices/dev-1/shares", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 1
    assert data["shares"][0]["permission"] == "control"


def test_non_owner_cannot_create_share(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    response = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-guest"),
        json={"permission": "view"},
    )
    assert response.status_code == 403


def test_accept_share_creates_guest_binding(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]

    accept = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accept.status_code == 200, accept.text
    assert accept.json()["device"]["deviceId"] == "dev-1"
    assert accept.json()["share"]["status"] == "accepted"

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
            ("dev-1", "a-guest"),
        ).fetchone()
        assert row is not None
        assert row["bind_mode"] == "shared"
        assert row["status"] == "active"


def test_guest_can_view_device(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    detail = client.get("/device/v1/app/devices/dev-1", headers=headers("a-guest"))
    assert detail.status_code == 200, detail.text
    assert detail.json()["deviceId"] == "dev-1"


def test_guest_cannot_control_with_view_share(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    response = client.put(
        "/device/v1/app/devices/dev-1",
        headers=headers("a-guest"),
        json={"firmwareVer": "2.0.0"},
    )
    assert response.status_code == 403


def test_guest_can_control_with_control_share(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "control"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    response = client.put(
        "/device/v1/app/devices/dev-1",
        headers=headers("a-guest"),
        json={"firmwareVer": "2.0.0"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["firmwareVer"] == "2.0.0"


def test_revoke_share_deactivates_binding(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    revoke = client.post(
        "/device/v1/app/devices/dev-1/share/revoke",
        headers=headers("a-owner"),
        json={"shareToken": token},
    )
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["status"] == "revoked"

    detail = client.get("/device/v1/app/devices/dev-1", headers=headers("a-guest"))
    assert detail.status_code == 403

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
            ("dev-1", "a-guest"),
        ).fetchone()
        assert row["status"] == "unbound"


def test_expired_share_cannot_be_accepted(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    past = "2020-01-01T00:00:00Z"
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view", "expiresAt": past},
    )
    assert create.status_code == 200
    token = create.json()["shareToken"]

    accept = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accept.status_code == 400
    assert accept.json()["message"] == "share token expired"


def test_accept_share_requires_pending_status(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    second = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert second.status_code == 404


def _accept_share(client, permission: str = "view") -> None:
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


def test_view_share_cannot_create_task(client):
    _accept_share(client, "view")
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-guest"),
        json={"text": "hello"},
    )
    assert response.status_code == 403


def test_view_share_cannot_preview_or_batch(client):
    _accept_share(client, "view")
    preview = client.post(
        "/device/v1/app/tasks/preview",
        headers=headers("a-guest"),
        json={"deviceId": "dev-1", "capability": "write_text", "params": {"text": "hi"}},
    )
    assert preview.status_code == 403

    batch = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        headers=headers("a-guest"),
        json={"tasks": [{"capability": "write_text", "params": {"text": "hi"}}]},
    )
    assert batch.status_code == 403


def test_view_share_cannot_execute_template_or_render_asset(client):
    _accept_share(client, "view")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_task_template
            (id, account_id, device_id, name, capability, params, category, use_count, created_at, updated_at)
            VALUES ('tpl-1', 'a-owner', 'dev-1', 't', 'write_text', '{}', 'custom', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO v2_asset_library
            (id, title, category, content, preview_url, tags, difficulty, created_at, use_count, status)
            VALUES ('asset-1', 'a', 'text', 'hi', '', '[]', 'easy', '2026-01-01T00:00:00Z', 0, 'active')
            """
        )
        conn.commit()

    execute = client.post(
        "/device/v1/app/tasks/templates/tpl-1/execute",
        headers=headers("a-guest"),
        json={"deviceId": "dev-1"},
    )
    assert execute.status_code == 403

    render = client.post(
        "/device/v1/app/assets/asset-1/render",
        headers=headers("a-guest"),
        json={"deviceId": "dev-1"},
    )
    assert render.status_code == 403


def test_control_share_can_create_task(client):
    _accept_share(client, "control")
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-guest"),
        json={"text": "hello"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["taskId"]
