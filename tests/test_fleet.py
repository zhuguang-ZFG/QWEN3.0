"""Tests for fleet management module."""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fleet.node_registry import (
    HEARTBEAT_TIMEOUT,
    NodeCapabilities,
    NodeRegistry,
)
from fleet.task_dispatcher import TaskDispatcher


# ─── Node registry tests ──────────────────────────────────────────────


class TestNodeRegistry:
    def test_register_node(self):
        reg = NodeRegistry()
        node = reg.register("gpu-box", host="192.168.1.1", port=8080, role="worker")
        assert node.node_id == "gpu-box"
        assert node.is_online

    def test_heartbeat(self):
        reg = NodeRegistry()
        reg.register("node-1")
        node = reg.heartbeat("node-1", load_avg=1.5)
        assert node is not None
        assert node.load_avg == 1.5

    def test_heartbeat_unknown_node(self):
        reg = NodeRegistry()
        assert reg.heartbeat("nonexistent") is None

    def test_online_nodes(self):
        reg = NodeRegistry()
        reg.register("a", role="worker")
        reg.register("b", role="worker")
        reg.register("c", role="head")
        online = reg.get_online_nodes(role="worker")
        assert len(online) == 2

    def test_offline_detection(self):
        reg = NodeRegistry()
        node = reg.register("old-node")
        # Simulate old heartbeat
        node.last_heartbeat = time.time() - HEARTBEAT_TIMEOUT - 10
        assert not node.is_online
        online = reg.get_online_nodes()
        assert len(online) == 0

    def test_capabilities(self):
        caps = NodeCapabilities(
            gpu=True,
            gpu_model="RTX 5060 Ti",
            gpu_vram_gb=16.0,
            cpu_cores=16,
            models=["ollama:qwen3"],
        )
        reg = NodeRegistry()
        node = reg.register("gpu-box", capabilities=caps)
        assert node.capabilities.gpu is True
        assert node.capabilities.gpu_vram_gb == 16.0
        assert "ollama:qwen3" in node.capabilities.models

    def test_to_dict(self):
        reg = NodeRegistry()
        reg.register("n1")
        d = reg.to_dict()
        assert "n1" in d
        assert d["n1"]["online"] is True

    def test_mark_completed(self):
        reg = NodeRegistry()
        reg.register("n1")
        reg.mark_completed("n1")
        assert reg.get_node("n1").tasks_completed == 1

    def test_sort_by_load(self):
        reg = NodeRegistry()
        reg.register("heavy")
        reg.register("light")
        reg.heartbeat("heavy", load_avg=5.0)
        reg.heartbeat("light", load_avg=0.5)
        nodes = reg.get_online_nodes()
        assert nodes[0].node_id == "light"
        assert nodes[1].node_id == "heavy"


# ─── Task dispatcher tests ────────────────────────────────────────────


class TestTaskDispatcher:
    def test_submit_task(self):
        d = TaskDispatcher()
        task = d.submit(task_type="shell", command="echo hello")
        assert task.status == "pending"
        assert task.task_id.startswith("fleet-")

    def test_dispatch_to_matching_node(self):
        d = TaskDispatcher()
        from fleet.node_registry import NodeRegistry

        reg = NodeRegistry()
        reg.register("worker-1")
        task = d.submit(task_type="shell", command="ls")
        result = d.dispatch(reg)
        assert result is not None
        task, node_id = result
        assert node_id == "worker-1"
        assert task.status == "assigned"

    def test_dispatch_gpu_task_to_cpu_node(self):
        d = TaskDispatcher()
        from fleet.node_registry import NodeRegistry

        reg = NodeRegistry()
        reg.register("cpu-only")  # no GPU
        d.submit(task_type="inference", command="run model", required_gpu=True)
        result = d.dispatch(reg)
        assert result is None  # no GPU node available

    def test_dispatch_gpu_task_to_gpu_node(self):
        d = TaskDispatcher()
        from fleet.node_registry import NodeRegistry

        reg = NodeRegistry()
        reg.register("gpu-node", capabilities=NodeCapabilities(gpu=True))
        d.submit(task_type="inference", command="run model", required_gpu=True)
        result = d.dispatch(reg)
        assert result is not None

    def test_dispatch_model_specific_task(self):
        d = TaskDispatcher()
        from fleet.node_registry import NodeRegistry

        reg = NodeRegistry()
        reg.register("w1", capabilities=NodeCapabilities(models=["ollama:qwen3"]))
        d.submit(task_type="inference", required_model="ollama:qwen3")
        result = d.dispatch(reg)
        assert result is not None

    def test_complete_task(self):
        d = TaskDispatcher()
        task = d.submit(task_type="shell", command="echo ok")
        ok = d.complete_task(task.task_id, result="ok")
        assert ok is True
        assert d.get_task(task.task_id).status == "completed"

    def test_complete_task_with_error(self):
        d = TaskDispatcher()
        task = d.submit(task_type="shell", command="fail")
        d.complete_task(task.task_id, error="exit 1")
        assert d.get_task(task.task_id).status == "failed"

    def test_cleanup_old_tasks(self):
        d = TaskDispatcher()
        task = d.submit(task_type="shell", command="echo")
        d.complete_task(task.task_id, result="done")
        # Simulate old task
        d.get_task(task.task_id).created_at = time.time() - 7200
        removed = d.cleanup(max_age=3600)
        assert removed == 1

    def test_no_nodes_no_dispatch(self):
        d = TaskDispatcher()
        d.submit(task_type="shell", command="echo")
        from fleet.node_registry import NodeRegistry

        reg = NodeRegistry()
        assert d.dispatch(reg) is None

    def test_busy_node_skipped(self):
        d = TaskDispatcher()
        from fleet.node_registry import NodeRegistry

        reg = NodeRegistry()
        node = reg.register("busy-worker")
        node.status = "busy"
        d.submit(task_type="shell", command="echo")
        # busy nodes should be skipped, but since only one node exists and
        # dispatch skips busy, it returns None
        result = d.dispatch(reg)
        assert result is None


# ─── Agent capability detection ───────────────────────────────────────


class TestFleetAgent:
    def test_detect_capabilities(self):
        from fleet.agent import detect_capabilities

        caps = detect_capabilities()
        assert "gpu" in caps
        assert "cpu_cores" in caps
        assert "shell" in caps
        assert isinstance(caps["models"], list)

    def test_run_shell_task_rejects_shell_metacharacters(self):
        from fleet.agent import run_shell_task

        result, error = run_shell_task("pytest -q; whoami")

        assert result == ""
        assert "unsafe command rejected" in error

    def test_run_shell_task_uses_safe_subprocess_boundary(self):
        from fleet.agent import run_shell_task

        with patch("fleet.agent.run_safe_command") as run:
            run.return_value.stdout = "ok\n"
            run.return_value.stderr = ""
            run.return_value.returncode = 0

            result, error = run_shell_task("pytest -q")

        assert result == "ok\n"
        assert error == ""
        assert run.call_args.kwargs["allowed_commands"]


# ─── Fleet API HTTP auth guard tests ────────────────────────────────


class TestFleetAPIAuth:
    """HTTP-level tests for /fleet/* token authentication."""

    def _make_app(self, admin_token: str = ""):
        from fastapi import FastAPI
        from routes.fleet_api import router, inject_state

        inject_state(admin_token=admin_token)
        app = FastAPI()
        app.include_router(router)
        return app

    def _client(self, admin_token: str = ""):
        from fastapi.testclient import TestClient

        return TestClient(self._make_app(admin_token))

    def test_no_token_configured_returns_503(self):
        """When server has no fleet token, all endpoints must reject."""
        resp = self._client(admin_token="").get("/fleet/nodes")
        assert resp.status_code == 503

    def test_missing_auth_header_returns_401(self):
        resp = self._client(admin_token="secret123").get("/fleet/nodes")
        assert resp.status_code == 401

    def test_invalid_bearer_token_returns_401(self):
        client = self._client(admin_token="secret123")
        resp = client.get("/fleet/nodes", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_valid_bearer_token_accepted(self):
        client = self._client(admin_token="secret123")
        resp = client.get("/fleet/nodes", headers={"Authorization": "Bearer secret123"})
        assert resp.status_code == 200

    def test_x_fleet_token_header_accepted(self):
        client = self._client(admin_token="secret123")
        resp = client.get("/fleet/nodes", headers={"X-Fleet-Token": "secret123"})
        assert resp.status_code == 200

    def test_register_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/register", json={"node_id": "n1"})
        assert resp.status_code == 401

    def test_submit_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/submit", json={"task_type": "shell"})
        assert resp.status_code == 401

    def test_poll_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.get("/fleet/poll/n1")
        assert resp.status_code == 401

    def test_complete_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/complete", json={"task_id": "t1"})
        assert resp.status_code == 401

    def test_heartbeat_requires_auth(self):
        client = self._client(admin_token="tok")
        resp = client.post("/fleet/heartbeat", json={"node_id": "n1"})
        assert resp.status_code == 401
