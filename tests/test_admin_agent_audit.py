import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin import router as admin_router
from routes.agent_tasks import _reset_for_tests, router as agent_router

app = FastAPI()
app.include_router(admin_router)
app.include_router(agent_router)
client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-admin-token"}


def setup_function():
    _reset_for_tests()


def test_admin_agent_audit_requires_auth():
    resp = client.get("/admin/api/agent-audit")
    assert resp.status_code in (401, 403)


def test_admin_agent_audit_returns_agent_tasks():
    task_id = client.post("/agent/tasks", json={
        "repo": "D:/GIT/deepcode-cli",
        "goal": "admin audit",
        "allowed_tools": ["git_diff"],
        "mode": "review",
    }, headers=HEADERS).json()["task_id"]

    resp = client.get("/admin/api/agent-audit", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["tasks"][0]["task_id"] == task_id
    assert data["tasks"][0]["status"] == "accepted"
