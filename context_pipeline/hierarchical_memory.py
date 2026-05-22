"""Hierarchical Memory — GenericAgent-inspired 5-layer memory system.

Replaces flat session_memory with structured layers:
- L0: Meta rules & routing constraints (immutable)
- L1: Performance index (latency, success rate per backend)
- L2: Global facts (backend availability, capabilities)
- L3: Routing skills/SOPs (crystallized successful paths)
- L4: Session archives (compressed conversation history)

Each layer has different update frequency and retrieval priority.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryLayer:
    """A single layer in the hierarchical memory system."""

    level: int
    name: str
    entries: dict[str, Any] = field(default_factory=dict)
    max_entries: int = 100

    def set(self, key: str, value: Any) -> None:
        self.entries[key] = value
        if len(self.entries) > self.max_entries:
            oldest_key = next(iter(self.entries))
            del self.entries[oldest_key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.entries.get(key, default)

    def search(self, query: str) -> list[tuple[str, Any]]:
        return [(k, v) for k, v in self.entries.items() if query.lower() in k.lower()]


class HierarchicalMemory:
    """5-layer memory system for intelligent routing decisions."""

    def __init__(self) -> None:
        self.L0 = MemoryLayer(0, "meta_rules", max_entries=50)
        self.L1 = MemoryLayer(1, "performance_index", max_entries=200)
        self.L2 = MemoryLayer(2, "global_facts", max_entries=100)
        self.L3 = MemoryLayer(3, "routing_skills", max_entries=500)
        self.L4 = MemoryLayer(4, "session_archives", max_entries=1000)

        self._init_meta_rules()

    def _init_meta_rules(self) -> None:
        """L0: Immutable routing constraints."""
        self.L0.set("max_retries", 3)
        self.L0.set("ensemble_max_backends", 3)
        self.L0.set("timeout_ms", 30000)
        self.L0.set("vision_requires_capable_backend", True)
        self.L0.set("ide_coding_min_tier", "strong")

    def update_performance(self, backend: str, latency_ms: int, success: bool) -> None:
        """L1: Update performance index for a backend."""
        key = f"perf:{backend}"
        stats = self.L1.get(key, {"total": 0, "success": 0, "avg_latency": 0})
        stats["total"] += 1
        if success:
            stats["success"] += 1
        n = stats["total"]
        stats["avg_latency"] = int(
            (stats["avg_latency"] * (n - 1) + latency_ms) / n
        )
        stats["success_rate"] = stats["success"] / stats["total"]
        self.L1.set(key, stats)

    def set_global_fact(self, key: str, value: Any) -> None:
        """L2: Store a global fact (backend availability, capabilities)."""
        self.L2.set(key, value)

    def store_skill(self, skill_key: str, skill_data: dict) -> None:
        """L3: Store a routing skill (crystallized successful path)."""
        self.L3.set(skill_key, skill_data)

    def find_skill(self, query: str) -> dict | None:
        """L3: Find a matching routing skill."""
        results = self.L3.search(query)
        if results:
            return results[0][1]
        return None

    def archive_session(self, session_id: str, summary: str) -> None:
        """L4: Archive a session summary."""
        self.L4.set(f"session:{session_id}", summary)

    def get_context_for_routing(self, backend: str, scenario: str) -> dict:
        """Retrieve relevant context across all layers for a routing decision."""
        context = {}
        context["rules"] = {
            "max_retries": self.L0.get("max_retries"),
            "timeout_ms": self.L0.get("timeout_ms"),
        }
        perf = self.L1.get(f"perf:{backend}")
        if perf:
            context["performance"] = perf
        context["scenario"] = scenario
        return context


# Singleton
_instance: HierarchicalMemory | None = None


def get_hierarchical_memory() -> HierarchicalMemory:
    global _instance
    if _instance is None:
        _instance = HierarchicalMemory()
    return _instance
