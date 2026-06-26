"""Rejection/auth tests for device task templates (split from test_device_app_task_templates)."""

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_app_task_templates_helpers import seed_second_device, template_id
from device_logic.db import connect


def test_template_auth_and_access_checks(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_binding(account_id="a-other", bind_mode="shared", binding_id="b-shared")

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "Private", "capability": "run_path", "deviceId": "dev-1", "params": {}},
    )
    tid = template_id(created)

    listed = client.get("/device/v1/app/tasks/templates", headers=headers("a-other"))
    assert listed.status_code == 200
    assert listed.json()["data"] == []

    assert (
        client.post(
            f"/device/v1/app/tasks/templates/{tid}/execute",
            headers=headers("a-other"),
            json={},
        ).status_code
        == 403
    )

    assert client.post("/device/v1/app/tasks/templates", headers={}).status_code == 401


def test_execute_template_rejects_unbound_device(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_second_device()
    with connect() as conn:
        conn.execute("DELETE FROM v2_device_binding WHERE device_id=?", ("dev-2",))
        conn.commit()

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "No Device", "capability": "run_path", "params": {}},
    )
    tid = template_id(created)

    executed = client.post(
        f"/device/v1/app/tasks/templates/{tid}/execute",
        headers=headers("a-owner"),
        json={"deviceId": "dev-2"},
    )
    assert executed.status_code == 403


def test_save_task_as_template_rejects_other_account_task(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_binding(account_id="a-other", bind_mode="shared", binding_id="b-shared")

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={"capability": "run_path", "params": {"path": [{"x": 0, "y": 0, "z": 0}]}},
    )
    task_id = created.json()["taskId"]

    saved = client.post(
        f"/device/v1/app/tasks/{task_id}/save-as-template",
        headers=headers("a-other"),
        json={"name": "Stolen"},
    )
    assert saved.status_code == 403


def test_create_template_rejects_unsupported_capability(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "Bad", "capability": "fly_to_moon"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "unsupported capability"


def test_execute_template_rejects_invalid_source_and_missing_device(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "No Device", "capability": "run_path", "params": {}},
    )
    tid = template_id(created)

    invalid_source = client.post(
        f"/device/v1/app/tasks/templates/{tid}/execute",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1", "source": "hacker"},
    )
    assert invalid_source.status_code == 400
    assert invalid_source.json()["message"] == "invalid source"

    missing_device = client.post(
        f"/device/v1/app/tasks/templates/{tid}/execute",
        headers=headers("a-owner"),
        json={},
    )
    assert missing_device.status_code == 400
    assert missing_device.json()["message"] == "device_id is required"

    not_found = client.post(
        "/device/v1/app/tasks/templates/non-existent/execute",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1"},
    )
    assert not_found.status_code == 404
