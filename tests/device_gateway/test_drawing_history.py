from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_artifacts.store import artifact_store
from device_gateway.tasks import create_task_from_transcript
from routes.device_gateway import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_drawing_history_returns_empty_for_new_device():
    """新设备的绘图历史为空"""
    response = _client().get(
        "/device/v1/devices/dev-new/history",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "dev-new"
    assert data["history"] == []
    assert data["count"] == 0


def test_drawing_history_returns_artifacts():
    """绘图历史返回制品"""
    # 创建一个任务并记录制品
    task = create_task_from_transcript("dev-1", "draw cat")
    artifact_store.put_artifact(
        task_id=task["task_id"],
        artifact_type="route_evidence",
        content={"device_id": "dev-1", "route_role": "device_draw"},
        retention_days=30,
    )

    response = _client().get(
        "/device/v1/devices/dev-1/history",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "dev-1"
    assert len(data["history"]) >= 1
    assert data["history"][0]["artifact_type"] == "route_evidence"


def test_drawing_history_filter_by_type():
    """按类型过滤绘图历史"""
    # 创建不同类型的制品
    task = create_task_from_transcript("dev-1", "draw star")
    artifact_store.put_artifact(
        task_id=task["task_id"],
        artifact_type="route_evidence",
        content={"device_id": "dev-1"},
        retention_days=30,
    )
    artifact_store.put_artifact(
        task_id=task["task_id"],
        artifact_type="preview_svg",
        content={"device_id": "dev-1", "svg": "<svg>...</svg>"},
        retention_days=30,
    )

    # 过滤 route_evidence
    response = _client().get(
        "/device/v1/devices/dev-1/history?artifact_type=route_evidence",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(h["artifact_type"] == "route_evidence" for h in data["history"])


def test_drawing_history_pagination():
    """绘图历史分页"""
    # 创建多个制品
    for i in range(5):
        task = create_task_from_transcript("dev-1", f"draw shape {i}")
        artifact_store.put_artifact(
            task_id=task["task_id"],
            artifact_type="route_evidence",
            content={"device_id": "dev-1", "index": i},
            retention_days=30,
        )

    # 测试分页
    response = _client().get(
        "/device/v1/devices/dev-1/history?limit=2&offset=0",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["history"]) == 2
    assert data["count"] == 2
    assert data["offset"] == 0
    assert data["limit"] == 2


def test_drawing_history_requires_auth():
    """查询绘图历史需要认证"""
    response = _client().get("/device/v1/devices/dev-1/history")
    assert response.status_code == 401 or response.status_code == 403
