import pytest

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


@pytest.fixture(autouse=True)
def _seed_db(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    return client


def _client(tmp_path, monkeypatch):
    return make_client(tmp_path, monkeypatch)


def test_preview_returns_shape(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/tasks/preview",
        headers=headers("a-owner"),
        json={
            "deviceId": "dev-1",
            "capability": "run_path",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 1, "z": 0}]},
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "preview" in data
    assert isinstance(data["preview"], str)
    assert "estimatedDuration" in data
    assert isinstance(data["estimatedDuration"], int)
    assert isinstance(data["pathPoints"], int)
    assert data["pathPoints"] >= 0


def test_preview_requires_device_access(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/tasks/preview",
        headers=headers("a-other"),
        json={"deviceId": "dev-1", "capability": "run_path", "params": {"path": []}},
    )

    assert response.status_code == 403


def test_preview_requires_auth(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/tasks/preview",
        json={"deviceId": "dev-1", "capability": "run_path", "params": {"path": []}},
    )

    assert response.status_code == 401


def test_preview_rejects_unsupported_capability(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/tasks/preview",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1", "capability": "unknown_action", "params": {}},
    )

    assert response.status_code == 400


def test_batch_creates_up_to_twenty_tasks(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)
    tasks = [{"capability": "run_path", "params": {"path": [{"x": i, "y": i, "z": 0}]}} for i in range(20)]

    response = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        headers=headers("a-owner"),
        json={"tasks": tasks},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 20
    assert len(data["tasks"]) == 20
    for item in data["tasks"]:
        assert "taskId" in item
        assert item["status"] == "approved"


def test_batch_rejects_more_than_twenty_tasks(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)
    tasks = [{"capability": "run_path", "params": {"path": [{"x": i, "y": i, "z": 0}]}} for i in range(21)]

    response = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        headers=headers("a-owner"),
        json={"tasks": tasks},
    )

    assert response.status_code == 400
    assert "max 20 tasks" in response.json()["message"]


def test_batch_requires_device_access(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        headers=headers("a-other"),
        json={"tasks": [{"capability": "run_path", "params": {"path": []}}]},
    )

    assert response.status_code == 403


def test_batch_requires_auth(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        json={"tasks": [{"capability": "run_path", "params": {"path": []}}]},
    )

    assert response.status_code == 401


def test_batch_handles_invalid_task_items(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        headers=headers("a-owner"),
        json={
            "tasks": [
                {"capability": "run_path", "params": {"path": [{"x": 0, "y": 0, "z": 0}]}},
                {"capability": "unsupported", "params": {}},
                "not-an-object",
            ]
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 3
    assert data["tasks"][0]["status"] == "approved"
    assert data["tasks"][1]["status"] == "failed"
    assert "error" in data["tasks"][1]
    assert data["tasks"][2]["status"] == "failed"


def test_batch_rejects_missing_tasks_array(tmp_path, monkeypatch):
    client, _store = _client(tmp_path, monkeypatch)

    response = client.post(
        "/device/v1/app/devices/dev-1/batch-tasks",
        headers=headers("a-owner"),
        json={},
    )

    assert response.status_code == 400
    assert "tasks array is required" in response.json()["message"]
