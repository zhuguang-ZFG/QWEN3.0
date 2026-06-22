"""Tests for context_pipeline/routing_bridge.py — routing outcome recording."""

from context_pipeline.routing_bridge import (
    RoutingDecision,
    select_backend_with_evolution,
    reflect_and_adjust,
    record_routing_outcome,
    get_metrics_snapshot,
)


class TestRoutingDecision:
    def test_default_values(self):
        d = RoutingDecision(backend="groq")
        assert d.backend == "groq"
        assert d.strategy == "default"
        assert d.confidence == 1.0
        assert d.reflection_notes is None


class TestSelectBackendWithEvolution:
    def test_returns_first_backend(self):
        d = select_backend_with_evolution(["a", "b", "c"], "chat")
        assert d.backend == "a"
        assert d.strategy == "fallback"

    def test_empty_list_returns_none(self):
        d = select_backend_with_evolution([], "chat")
        assert d.backend == "none"
        assert d.confidence == 0.0

    def test_returns_routing_decision(self):
        d = select_backend_with_evolution(["groq"], "coding")
        assert isinstance(d, RoutingDecision)


class TestReflectAndAdjust:
    def test_returns_unchanged(self):
        d = reflect_and_adjust("groq", 150, True, "chat")
        assert d.backend == "groq"
        assert d.strategy == "unchanged"

    def test_handles_failure(self):
        d = reflect_and_adjust("groq", 999, False, "chat")
        assert d.backend == "groq"


class TestRecordRoutingOutcome:
    def test_skip_weights_does_not_raise(self):
        record_routing_outcome("groq", 150, True, "chat", skip_weights=True)

    def test_without_skip_does_not_raise(self):
        record_routing_outcome("groq", 150, True, "chat")


class TestGetMetricsSnapshot:
    def test_returns_empty_dict(self):
        assert get_metrics_snapshot() == {}
