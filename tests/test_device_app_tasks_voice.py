from device_logic.db import connect
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


def test_device_app_voice_review_paths(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_binding(account_id="a-other", bind_mode="shared", binding_id="b-shared")

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "run_path",
            "source": "voice",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "requireApproval": True},
        },
    )
    task_id = created.json()["taskId"]
    assert (
        client.post("/device/v1/app/devices/dev-1/voice-tasks/pending", headers=headers("a-other"), json={}).status_code
        == 403
    )
    assert (
        client.post(f"/device/v1/app/tasks/{task_id}/approve", headers=headers("a-other"), json={}).status_code == 403
    )
    assert client.post(f"/device/v1/app/tasks/{task_id}/reject", headers=headers("a-other"), json={}).status_code == 403

    store.reset()
    approved = client.post(f"/device/v1/app/tasks/{task_id}/approve", headers=headers("a-owner"), json={})
    assert approved.status_code == 409
    assert approved.json()["message"] == "task dispatch payload is unavailable"
    with connect() as conn:
        row = conn.execute("SELECT status FROM v2_task WHERE id=?", (task_id,)).fetchone()
    assert row["status"] == "pending"


def test_control_share_cannot_approve_voice_task(tmp_path, monkeypatch):
    from device_app_sharing_helpers import seed_guest

    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create_share = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "control"},
    )
    assert create_share.status_code == 200, create_share.text
    token = create_share.json()["shareToken"]
    accepted = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accepted.status_code == 200, accepted.text

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "run_path",
            "source": "voice",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "requireApproval": True},
        },
    )
    task_id = created.json()["taskId"]
    assert (
        client.post("/device/v1/app/devices/dev-1/voice-tasks/pending", headers=headers("a-guest"), json={}).status_code
        == 403
    )
    assert (
        client.post(f"/device/v1/app/tasks/{task_id}/approve", headers=headers("a-guest"), json={}).status_code == 403
    )
    assert client.post(f"/device/v1/app/tasks/{task_id}/reject", headers=headers("a-guest"), json={}).status_code == 403


def test_device_app_reject_pending_voice_task(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "run_path",
            "source": "voice",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "requireApproval": True},
        },
    )

    rejected = client.post(
        f"/device/v1/app/tasks/{created.json()['taskId']}/reject", headers=headers("a-owner"), json={"reason": "no"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reason"] == "no"


def test_device_app_draw_generated_image_url(tmp_path, monkeypatch):
    """draw_generated with imageUrl creates a task that converts the image to a motion path."""
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    async def fake_handle_device_draw(prompt: str, device_id: str, **kwargs: object):
        return {
            "status": "success",
            "svg_path": "M0,0 L10,0 L10,10",
            "image_url": "https://example.com/input.jpg",
            "model": "mock",
        }

    monkeypatch.setattr("device_gateway.task_draw_params.handle_device_draw", fake_handle_device_draw)

    created = client.post(
        "/device/v1/app/devices/dev-1/tasks",
        headers=headers("a-owner"),
        json={
            "capability": "draw_generated",
            "source": "client",
            "params": {
                "imageUrl": "https://api.telegram.org/file/bot123/input.jpg",
                "feed": 500,
            },
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["task"]["app_capability"] == "draw_generated"
    assert data["task"]["params"]["feed"] == 500
    assert data["task"]["params"]["source_capability"] == "draw_generated"
