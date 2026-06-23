"""Tests for fleet.node_registry."""

from __future__ import annotations

import time
import pytest

MOCK_NOW = 2_000_000_000.0

from fleet.node_registry import (
    HEARTBEAT_TIMEOUT,
    NodeCapabilities,
    NodeRegistry,
)


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
        node.last_heartbeat = MOCK_NOW - HEARTBEAT_TIMEOUT - 10
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


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
