"""Node registry — tracks all fleet nodes, their capabilities, and health."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT = 90  # seconds — node marked offline after this


@dataclass
class NodeCapabilities:
    gpu: bool = False
    gpu_model: str = ""
    gpu_vram_gb: float = 0.0
    cpu_cores: int = 0
    ram_gb: float = 0.0
    shell: bool = True
    workspace: bool = True
    models: list[str] = field(default_factory=list)  # e.g. ["ollama:qwen3"]


@dataclass
class NodeInfo:
    node_id: str
    host: str = ""
    port: int = 0
    role: str = "worker"  # head, worker
    capabilities: NodeCapabilities = field(default_factory=NodeCapabilities)
    status: str = "offline"  # online, offline, busy
    load_avg: float = 0.0
    last_heartbeat: float = 0.0
    registered_at: float = field(default_factory=time.time)
    tasks_completed: int = 0
    tasks_failed: int = 0

    @property
    def is_online(self) -> bool:
        return (time.time() - self.last_heartbeat) < HEARTBEAT_TIMEOUT

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "role": self.role,
            "status": self.status if self.is_online else "offline",
            "gpu": self.capabilities.gpu,
            "gpu_model": self.capabilities.gpu_model,
            "gpu_vram_gb": self.capabilities.gpu_vram_gb,
            "cpu_cores": self.capabilities.cpu_cores,
            "shell": self.capabilities.shell,
            "workspace": self.capabilities.workspace,
            "models": self.capabilities.models,
            "load_avg": self.load_avg,
            "last_heartbeat": self.last_heartbeat,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "online": self.is_online,
        }


class NodeRegistry:
    """In-memory registry of all fleet nodes."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeInfo] = {}

    def register(
        self,
        node_id: str,
        host: str = "",
        port: int = 0,
        role: str = "worker",
        capabilities: NodeCapabilities | None = None,
    ) -> NodeInfo:
        now = time.time()
        if node_id in self._nodes:
            node = self._nodes[node_id]
            node.host = host or node.host
            node.port = port or node.port
            node.last_heartbeat = now
            node.status = "online"
            if capabilities:
                node.capabilities = capabilities
        else:
            node = NodeInfo(
                node_id=node_id, host=host, port=port, role=role,
                capabilities=capabilities or NodeCapabilities(),
                last_heartbeat=now,
            )
            self._nodes[node_id] = node
            _log.info("fleet: node registered id=%s host=%s role=%s", node_id, host, role)
        return node

    def heartbeat(
        self,
        node_id: str,
        load_avg: float = 0.0,
        status: str = "online",
    ) -> NodeInfo | None:
        node = self._nodes.get(node_id)
        if node is None:
            return None
        node.last_heartbeat = time.time()
        node.load_avg = load_avg
        node.status = status
        return node

    def get_node(self, node_id: str) -> NodeInfo | None:
        return self._nodes.get(node_id)

    def get_online_nodes(self, role: str = "") -> list[NodeInfo]:
        nodes = [n for n in self._nodes.values() if n.is_online]
        if role:
            nodes = [n for n in nodes if n.role == role]
        return sorted(nodes, key=lambda n: (n.load_avg, -n.capabilities.gpu_vram_gb))

    def get_all_nodes(self) -> list[NodeInfo]:
        return list(self._nodes.values())

    def mark_completed(self, node_id: str) -> None:
        node = self._nodes.get(node_id)
        if node:
            node.tasks_completed += 1

    def mark_failed(self, node_id: str) -> None:
        node = self._nodes.get(node_id)
        if node:
            node.tasks_failed += 1

    def to_dict(self) -> dict:
        return {nid: node.to_dict() for nid, node in self._nodes.items()}


_registry = NodeRegistry()


def get_registry() -> NodeRegistry:
    return _registry
