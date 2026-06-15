"""Tests for M3: context pipeline integration — routing bridge."""

from __future__ import annotations

from context_pipeline.routing_bridge import (
    select_backend_with_evolution,
    reflect_and_adjust,
    record_routing_outcome,
    get_metrics_snapshot,
)


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

    def test_get_metrics_snapshot(self):
        snap = get_metrics_snapshot()
        assert snap == {}
