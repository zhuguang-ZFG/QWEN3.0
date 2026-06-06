"""Tests for M3: context pipeline integration — persistence, routing bridge."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from context_pipeline.hierarchical_memory import HierarchicalMemory, get_hierarchical_memory
from context_pipeline.memory_persistence import MemoryPersistence, load_hierarchical_memory, save_hierarchical_memory
from context_pipeline.routing_bridge import (
    RoutingDecision,
    get_metrics_snapshot,
    record_routing_outcome,
    reflect_and_adjust,
    select_backend_with_evolution,
)


class TestMemoryPersistence:
    def test_save_and_load_layer(self, tmp_path):
        db = str(tmp_path / "test.db")
        p = MemoryPersistence(db)
        p.save_layer(1, {"perf:gpt4": {"total": 10, "success": 8}})
        loaded = p.load_layer(1)
        assert "perf:gpt4" in loaded
        assert loaded["perf:gpt4"]["total"] == 10
        p.close()

    def test_snapshot_all(self, tmp_path):
        db = str(tmp_path / "snap.db")
        p = MemoryPersistence(db)
        p.save_layer(0, {"max_retries": 3})
        p.save_layer(3, {"skill:fast_route": {"backend": "groq"}})
        snap = p.snapshot_all()
        assert 0 in snap
        assert 3 in snap
        assert snap[0]["max_retries"] == 3
        p.close()

    def test_layer_stats(self, tmp_path):
        db = str(tmp_path / "stats.db")
        p = MemoryPersistence(db)
        p.save_layer(1, {"a": 1, "b": 2})
        p.save_layer(3, {"c": 3})
        stats = p.layer_stats()
        assert stats[1] == 2
        assert stats[3] == 1
        p.close()

    def test_clear_layer(self, tmp_path):
        db = str(tmp_path / "clear.db")
        p = MemoryPersistence(db)
        p.save_layer(1, {"x": 1})
        p.clear_layer(1)
        assert p.load_layer(1) == {}
        p.close()


class TestHierarchicalMemoryPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        db = str(tmp_path / "hmem.db")
        hmem1 = HierarchicalMemory()
        hmem1.update_performance("groq", 150, True)
        hmem1.store_skill("fast_route", {"backend": "groq"})
        save_hierarchical_memory(hmem1, MemoryPersistence(db))

        hmem2 = HierarchicalMemory()
        load_hierarchical_memory(hmem2, MemoryPersistence(db))
        perf = hmem2.L1.get("perf:groq")
        assert perf is not None
        assert perf["total"] == 1
        skill = hmem2.L3.get("fast_route")
        assert skill is not None
        assert skill["backend"] == "groq"

    def test_save_load_via_methods(self, tmp_path):
        db = str(tmp_path / "hmem2.db")
        hmem = HierarchicalMemory()
        hmem.update_performance("test", 200, True)
        hmem.save(db)
        hmem.L1.entries.clear()
        hmem.load(db)
        assert hmem.L1.get("perf:test") is not None


class TestRoutingBridge:
    def test_select_backend_fallback(self):
        result = select_backend_with_evolution(["groq", "nvidia"], "chat")
        assert result.backend in ("groq", "nvidia")
        assert result.strategy in ("default", "fallback")

    def test_select_backend_empty(self):
        result = select_backend_with_evolution([], "chat")
        assert result.backend == "none"
        assert result.confidence == 0.0

    def test_reflect_unchanged(self):
        result = reflect_and_adjust("groq", 100, True, "chat")
        assert result.backend == "groq"

    def test_record_outcome(self):
        record_routing_outcome("groq", 150, True, "coding")
        hmem = get_hierarchical_memory()
        perf = hmem.L1.get("perf:groq")
        assert perf is not None

    def test_get_metrics_snapshot(self):
        hmem = get_hierarchical_memory()
        hmem.update_performance("test_backend", 100, True)
        snap = get_metrics_snapshot()
        assert "backends" in snap
