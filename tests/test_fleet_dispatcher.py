"""Tests for fleet.task_dispatcher."""

from __future__ import annotations

import time
import pytest

MOCK_NOW = 2_000_000_000.0

from fleet.node_registry import NodeCapabilities, NodeRegistry
from fleet.task_dispatcher import TaskDispatcher


class TestTaskDispatcher:
    def test_submit_task(self):
        d = TaskDispatcher()
        task = d.submit(task_type="shell", command="echo hello")
        assert task.status == "pending"
        assert task.task_id.startswith("fleet-")

    def test_dispatch_to_matching_node(self):
        d = TaskDispatcher()
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
        reg = NodeRegistry()
        reg.register("cpu-only")  # no GPU
        d.submit(task_type="inference", command="run model", required_gpu=True)
        result = d.dispatch(reg)
        assert result is None  # no GPU node available

    def test_dispatch_gpu_task_to_gpu_node(self):
        d = TaskDispatcher()
        reg = NodeRegistry()
        reg.register("gpu-node", capabilities=NodeCapabilities(gpu=True))
        d.submit(task_type="inference", command="run model", required_gpu=True)
        result = d.dispatch(reg)
        assert result is not None

    def test_dispatch_model_specific_task(self):
        d = TaskDispatcher()
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
        d.get_task(task.task_id).created_at = MOCK_NOW - 7200
        removed = d.cleanup(max_age=3600)
        assert removed == 1

    def test_no_nodes_no_dispatch(self):
        d = TaskDispatcher()
        d.submit(task_type="shell", command="echo")
        reg = NodeRegistry()
        assert d.dispatch(reg) is None

    def test_busy_node_skipped(self):
        d = TaskDispatcher()
        reg = NodeRegistry()
        node = reg.register("busy-worker")
        node.status = "busy"
        d.submit(task_type="shell", command="echo")
        # busy nodes should be skipped, but since only one node exists and
        # dispatch skips busy, it returns None
        result = d.dispatch(reg)
        assert result is None


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
