from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.tasks import create_task_from_transcript
from routes.device_gateway import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_task_status_returns_404_for_nonexistent():
    """查询不存在的任务返回 404"""
    response = _client().get(
        "/device/v1/tasks/nonexistent-task-id",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 404


def test_task_status_returns_task_info():
    """查询存在的任务返回任务信息"""
    # 先创建一个任务
    task = create_task_from_transcript("dev-1", "home")

    response = _client().get(
        f"/device/v1/tasks/{task['task_id']}",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task["task_id"]
    assert "status" in data
    assert "task" in data


def test_task_list_returns_tasks():
    """查询任务列表返回任务"""
    # 创建一些任务
    create_task_from_transcript("dev-1", "home")
    create_task_from_transcript("dev-1", "write Hello")

    response = _client().get(
        "/device/v1/tasks?device_id=dev-1",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "count" in data
    assert data["count"] >= 2


def test_task_list_filter_by_status():
    """按状态过滤任务列表"""
    # 创建任务
    create_task_from_transcript("dev-1", "home")

    response = _client().get(
        "/device/v1/tasks?device_id=dev-1&status=created",
        headers={"Authorization": "Bearer test-private-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    # 所有返回的任务都应该是 created 状态
    for task in data["tasks"]:
        assert task.get("status") == "created"


def test_task_list_requires_auth():
    """查询任务列表需要认证"""
    response = _client().get("/device/v1/tasks")
    assert response.status_code == 401 or response.status_code == 403


def test_task_status_requires_auth():
    """查询任务状态需要认证"""
    response = _client().get("/device/v1/tasks/test-task-id")
    assert response.status_code == 401 or response.status_code == 403
