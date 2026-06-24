from device_logic.db import connect
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


def _template_id(response) -> str:
    return response.json()["data"]["templateId"]


def _seed_second_device(device_id: str = "dev-2", device_sn: str = "SN-APP-02") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver) VALUES (?, ?, 'esp32s3_xyz', '1.0.0', 'rev-a')",
            (device_id, device_sn),
        )
        conn.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES (?, ?, ?, 'owner', 'active')",
            (f"b-{device_id}", device_id, "a-owner"),
        )
        conn.commit()


def test_create_task_template(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={
            "name": "Draw Circle",
            "capability": "run_path",
            "deviceId": "dev-1",
            "category": "favorite",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}]},
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["name"] == "Draw Circle"
    assert data["capability"] == "run_path"
    assert data["category"] == "favorite"
    assert data["deviceId"] == "dev-1"
    assert data["params"]["path"][0]["x"] == 0
    assert data["useCount"] == 0


def test_create_template_rejects_invalid_category(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "X", "capability": "run_path", "category": "invalid"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "invalid category"


def test_create_template_rejects_missing_name_or_capability(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    missing_name = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"capability": "run_path"},
    )
    assert missing_name.status_code == 400
    assert missing_name.json()["message"] == "name and capability are required"


def test_list_task_templates_with_filters(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "T1", "capability": "run_path", "deviceId": "dev-1", "category": "custom"},
    )
    client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "T2", "capability": "home", "category": "favorite"},
    )

    all_templates = client.get("/device/v1/app/tasks/templates", headers=headers("a-owner"))
    assert all_templates.status_code == 200, all_templates.text
    assert len(all_templates.json()["data"]) == 2

    filtered = client.get("/device/v1/app/tasks/templates?device_id=dev-1", headers=headers("a-owner"))
    assert len(filtered.json()["data"]) == 1
    assert filtered.json()["data"][0]["name"] == "T1"

    favorite = client.get("/device/v1/app/tasks/templates?category=favorite", headers=headers("a-owner"))
    assert len(favorite.json()["data"]) == 1
    assert favorite.json()["data"][0]["name"] == "T2"


def test_execute_template_creates_task(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={
            "name": "Execute Me",
            "capability": "run_path",
            "deviceId": "dev-1",
            "params": {"path": [{"x": 1, "y": 2, "z": 0}]},
        },
    )
    template_id = _template_id(created)

    executed = client.post(
        f"/device/v1/app/tasks/templates/{template_id}/execute",
        headers=headers("a-owner"),
        json={"source": "api", "requestId": "req-exec-001"},
    )
    assert executed.status_code == 200, executed.text
    data = executed.json()["data"]
    assert data["capability"] == "run_path"
    assert data["deviceId"] == "dev-1"
    assert data["dispatchStatus"] == "queued"
    assert data["taskId"]

    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (data["taskId"],)).fetchone()
    assert row is not None
    assert row["intent"] == "run_path"
    assert row["device_id"] == "dev-1"

    detail = client.get(f"/device/v1/app/tasks/{data['taskId']}", headers=headers("a-owner"))
    assert detail.status_code == 200
    assert isinstance(detail.json()["params"], dict)

    listed = client.get("/device/v1/app/tasks/templates", headers=headers("a-owner"))
    assert listed.json()["data"][0]["useCount"] == 1


def test_execute_template_allows_device_override(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    _seed_second_device()

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "Override", "capability": "run_path", "params": {"path": [{"x": 0, "y": 0, "z": 0}]}},
    )
    template_id = _template_id(created)

    executed = client.post(
        f"/device/v1/app/tasks/templates/{template_id}/execute",
        headers=headers("a-owner"),
        json={"deviceId": "dev-2"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["data"]["deviceId"] == "dev-2"


def test_save_task_as_template(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "run_path",
            "requestId": "req-save-001",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}]},
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["taskId"]

    saved = client.post(
        f"/device/v1/app/tasks/{task_id}/save-as-template",
        headers=headers("a-owner"),
        json={"name": "Saved Template", "category": "recent"},
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["name"] == "Saved Template"
    assert data["capability"] == "run_path"
    assert data["category"] == "recent"
    assert data["deviceId"] == "dev-1"
    assert isinstance(data["params"], dict)


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
    template_id = _template_id(created)

    listed = client.get("/device/v1/app/tasks/templates", headers=headers("a-other"))
    assert listed.status_code == 200
    assert listed.json()["data"] == []

    assert (
        client.post(
            f"/device/v1/app/tasks/templates/{template_id}/execute",
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
    _seed_second_device()
    with connect() as conn:
        conn.execute("DELETE FROM v2_device_binding WHERE device_id=?", ("dev-2",))
        conn.commit()

    created = client.post(
        "/device/v1/app/tasks/templates",
        headers=headers("a-owner"),
        json={"name": "No Device", "capability": "run_path", "params": {}},
    )
    template_id = _template_id(created)

    executed = client.post(
        f"/device/v1/app/tasks/templates/{template_id}/execute",
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
    template_id = _template_id(created)

    invalid_source = client.post(
        f"/device/v1/app/tasks/templates/{template_id}/execute",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1", "source": "hacker"},
    )
    assert invalid_source.status_code == 400
    assert invalid_source.json()["message"] == "invalid source"

    missing_device = client.post(
        f"/device/v1/app/tasks/templates/{template_id}/execute",
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
