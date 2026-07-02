"""Permission tests for device app sharing (split from test_device_app_sharing)."""

from device_app_helpers import headers
from device_app_sharing_helpers import accept_share
from device_app_sharing_helpers import client  # noqa: F401  pytest fixture injected via parameter name (d)
from device_logic.db import connect


def test_view_share_cannot_create_task(client):
    accept_share(client, "view")
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-guest"),
        json={"text": "hello"},
    )
    assert response.status_code == 403


def test_view_share_cannot_preview_or_batch(client):
    accept_share(client, "view")
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
    accept_share(client, "view")
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
    accept_share(client, "control")
    response = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-guest"),
        json={"text": "hello"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["taskId"]
