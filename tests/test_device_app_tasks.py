from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


def test_device_app_task_list_and_detail_are_scoped_to_bound_devices(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    store.create_task_state(
        {
            "type": "motion_task",
            "task_id": "task-001",
            "device_id": "dev-1",
            "capability": "run_path",
            "source": "voice",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}]},
            "request_id": "req-001",
        },
        status="queued",
    )
    store.record_motion_event({"type": "motion_event", "device_id": "dev-1", "task_id": "task-001", "phase": "running"})

    listed = client.get("/device/v1/app/tasks?device_id=dev-1", headers=headers("a-owner"))
    assert listed.status_code == 200, listed.text
    assert listed.json()["tasks"][0]["taskId"] == "task-001"
    assert listed.json()["tasks"][0]["status"] == "running"

    detail = client.get("/device/v1/app/tasks/task-001", headers=headers("a-owner"))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["params"]["path"][0]["x"] == 0
    assert payload["events"][0]["phase"] == "running"

    assert client.get("/device/v1/app/tasks?device_id=dev-1", headers=headers("a-other")).status_code == 403
    assert client.get("/device/v1/app/tasks/task-001", headers=headers("a-other")).status_code == 403


def test_device_app_task_list_rejects_invalid_limit(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.get("/device/v1/app/tasks?device_id=dev-1&limit=-1", headers=headers("a-owner"))

    assert response.status_code == 422


def test_device_app_task_list_accepts_deviceId_alias(tmp_path, monkeypatch):
    """Mini-program sends camelCase deviceId; must not 422."""
    client, store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    store.create_task_state(
        {
            "type": "motion_task",
            "task_id": "task-camel",
            "device_id": "dev-1",
            "capability": "run_path",
            "source": "voice",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}]},
            "request_id": "req-camel",
        },
        status="queued",
    )

    listed = client.get("/device/v1/app/tasks?deviceId=dev-1", headers=headers("a-owner"))
    assert listed.status_code == 200, listed.text
    assert listed.json()["tasks"][0]["taskId"] == "task-camel"


def test_device_app_task_list_requires_device_id(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.get("/device/v1/app/tasks", headers=headers("a-owner"))
    assert response.status_code == 400


def test_device_app_create_task_uses_native_gateway_route(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={"text": "write hello", "requestId": "req-app-001"},
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["status"] == "queued_no_delivery"
    assert data["queueDepth"] == 1
    assert data["task"]["request_id"] == "req-app-001"
    assert data["taskId"] == data["task"]["task_id"]


def test_device_app_create_capability_task_lists_and_approves(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "run_path",
            "source": "voice",
            "requestId": "req-voice-001",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "requireApproval": True},
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["status"] == "pending"
    assert data["dispatchStatus"] == "waiting_approval"

    pending = client.post("/device/v1/app/devices/dev-1/voice-tasks/pending", headers=headers("a-owner"), json={})
    assert pending.status_code == 200, pending.text
    assert pending.json()["tasks"][0]["taskId"] == data["taskId"]

    approved = client.post(
        f"/device/v1/app/tasks/{data['taskId']}/approve", headers=headers("a-owner"), json={"reason": "ok"}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["dispatchStatus"] == "queued_no_delivery"


def test_device_app_create_task_validation_paths(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    invalid = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={"capability": "run_path", "source": "cli", "params": {"path": [{"x": 0, "y": 0, "z": 0}]}},
    )
    assert invalid.status_code == 400
    assert invalid.json()["message"] == "invalid source"

    alias = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "draw_image",
            "requestId": "req-draw-alias",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "prompt": "circle"},
        },
    )
    assert alias.status_code == 200, alias.text
    assert alias.json()["capability"] == "draw_generated"
    assert alias.json()["requestId"] == "req-draw-alias"


def test_device_app_db_task_payload_keeps_object_params_and_request_id(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "run_path",
            "requestId": "req-row-payload",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "constraints": {"profile": "child-safe"}},
        },
    )
    assert created.status_code == 200, created.text

    listed = client.get("/device/v1/app/tasks?device_id=dev-1", headers=headers("a-owner"))
    row = next(task for task in listed.json()["tasks"] if task["taskId"] == created.json()["taskId"])
    assert isinstance(row["params"], dict)
    assert row["requestId"] == "req-row-payload"
    assert '"profile": "child-safe"' in row["constraintsJson"]
