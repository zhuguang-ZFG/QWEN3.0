import pytest

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_gateway.coordinator import MultiDeviceCoordinator
from device_gateway.sessions import DeviceSession, registry
from device_logic.db import connect


def seed_device_unbound(device_id: str = "dev-2", device_sn: str = "SN-APP-02") -> None:
    """Create a device with no account binding."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver)
            VALUES (?, ?, 'esp32s3_xyz', '1.0.0', 'rev-a')
            """,
            (device_id, device_sn),
        )
        conn.commit()


SAMPLE_SVG = (
    '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg"><g><rect width="200" height="200"/></g></svg>'
)


def test_grid_split_produces_expected_regions():
    coordinator = MultiDeviceCoordinator()
    bounds = {"x": 0, "y": 0, "width": 200, "height": 200}
    regions = coordinator._grid_split(bounds, 4)

    assert len(regions) == 4
    assert regions[0] == {"x": 0, "y": 0, "width": 100.0, "height": 100.0}
    assert regions[1] == {"x": 100.0, "y": 0, "width": 100.0, "height": 100.0}
    assert regions[2] == {"x": 0, "y": 100.0, "width": 100.0, "height": 100.0}
    assert regions[3] == {"x": 100.0, "y": 100.0, "width": 100.0, "height": 100.0}


def test_grid_split_with_non_square_device_count():
    coordinator = MultiDeviceCoordinator()
    bounds = {"x": 0, "y": 0, "width": 300, "height": 200}
    regions = coordinator._grid_split(bounds, 3)

    assert len(regions) == 3
    assert regions[0]["width"] == pytest.approx(150.0)
    assert regions[0]["height"] == pytest.approx(100.0)


def test_clip_svg_contains_clip_path():
    coordinator = MultiDeviceCoordinator()
    region = {"x": 0, "y": 0, "width": 100, "height": 100}
    clipped = coordinator._clip_svg(SAMPLE_SVG, region)

    assert '<defs><clipPath id="clip_0_0">' in clipped
    assert '<rect x="0" y="0" width="100" height="100"/>' in clipped
    assert 'clip-path="url(#clip_0_0)"' in clipped


def test_assign_devices_maps_ids():
    coordinator = MultiDeviceCoordinator()
    regions = [{"x": 0, "y": 0, "width": 100, "height": 100}]
    assignments = coordinator.assign_devices(regions, ["dev-a"])

    assert len(assignments) == 1
    assert assignments[0]["device_id"] == "dev-a"
    assert assignments[0]["device_index"] == 0
    assert assignments[0]["region"]["x"] == 0


def test_merge_results_summary():
    coordinator = MultiDeviceCoordinator()
    results = [
        {"device_id": "d1", "status": "completed"},
        {"device_id": "d2", "status": "completed"},
        {"device_id": "d3", "status": "failed"},
    ]
    summary = coordinator.merge_results(results)

    assert summary["total_devices"] == 3
    assert summary["success_count"] == 2
    assert summary["failed_count"] == 1
    assert summary["overall_status"] == "partial"


def test_merge_results_all_completed():
    coordinator = MultiDeviceCoordinator()
    results = [{"device_id": "d1", "status": "completed"}]
    summary = coordinator.merge_results(results)

    assert summary["overall_status"] == "completed"


def test_merge_results_empty():
    coordinator = MultiDeviceCoordinator()
    summary = coordinator.merge_results([])

    assert summary["overall_status"] == "empty"


@pytest.mark.asyncio
async def test_execute_coordinated_offline_device_records_failure():
    coordinator = MultiDeviceCoordinator()
    registry.clear()
    result = await coordinator.execute_coordinated(SAMPLE_SVG, ["dev-offline"], "coord-1")

    assert result["coordinator_id"] == "coord-1"
    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["error"] == "device_offline"
    assert result["summary"]["failed_count"] == 1


def test_batch_draw_endpoint_rejects_unauthorized_device(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    seed_device_unbound(device_id="dev-2", device_sn="SN-APP-02")
    # no binding for dev-2

    response = client.post(
        "/device/v1/app/devices/batch-draw",
        headers=headers("a-owner"),
        json={
            "device_ids": ["dev-1", "dev-2"],
            "svg": SAMPLE_SVG,
            "coordinator_id": "coord-batch-1",
        },
    )
    assert response.status_code == 403


def test_batch_draw_endpoint_dispatches_to_online_devices(tmp_path, monkeypatch):
    client, store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    registry.clear()
    registry.register(DeviceSession(device_id="dev-1", websocket=None))

    response = client.post(
        "/device/v1/app/devices/batch-draw",
        headers=headers("a-owner"),
        json={
            "device_ids": ["dev-1"],
            "svg": SAMPLE_SVG,
            "coordinator_id": "coord-batch-2",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["coordinator_id"] == "coord-batch-2"
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] == "dispatched"
    assert data["summary"]["overall_status"] == "partial"

    snapshot = store.task_snapshot(data["results"][0]["task_id"])
    assert snapshot is not None
    task = snapshot["task"]
    assert task["capability"] == "draw_svg"
    assert task["batch_id"] == data["batch_id"]
    assert "svg" in task["params"]


def test_batch_draw_endpoint_offline_device_records_failure(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    registry.clear()

    response = client.post(
        "/device/v1/app/devices/batch-draw",
        headers=headers("a-owner"),
        json={
            "device_ids": ["dev-1"],
            "svg": SAMPLE_SVG,
            "coordinator_id": "coord-batch-3",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["results"][0]["status"] == "failed"
    assert data["results"][0]["error"] == "device_offline"
    assert data["summary"]["failed_count"] == 1


def test_batch_draw_endpoint_requires_fields(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    response = client.post(
        "/device/v1/app/devices/batch-draw",
        headers=headers("a-owner"),
        json={"device_ids": [], "svg": SAMPLE_SVG, "coordinator_id": "c"},
    )
    assert response.status_code == 400
