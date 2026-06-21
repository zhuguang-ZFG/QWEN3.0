"""Tests for context_pipeline.routing_bridge (retired evolution hooks + weights recording)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from context_pipeline.routing_bridge import (
    RoutingDecision,
    get_metrics_snapshot,
    record_routing_outcome,
    reflect_and_adjust,
    select_backend_with_evolution,
)


def test_select_backend_with_evolution_picks_first():
    decision = select_backend_with_evolution(["groq-fast", "nvidia-code"], scenario="coding")
    assert decision.backend == "groq-fast"
    assert decision.strategy == "fallback"
    assert decision.confidence == 1.0


def test_select_backend_with_evolution_empty_list():
    decision = select_backend_with_evolution([], scenario="chat")
    assert decision.backend == "none"
    assert decision.confidence == 0.0


def test_reflect_and_adjust_is_stable():
    decision = reflect_and_adjust("groq-fast", latency_ms=120, success=True, scenario="coding")
    assert decision.backend == "groq-fast"
    assert decision.strategy == "unchanged"


def test_get_metrics_snapshot_returns_empty_dict():
    assert get_metrics_snapshot() == {}


@patch("context_pipeline.routing_weights.get_routing_weights")
def test_record_routing_outcome_success(mock_get_weights):
    weights = MagicMock()
    mock_get_weights.return_value = weights
    record_routing_outcome("groq-fast", latency_ms=50, success=True, scenario="coding")
    weights.record_success.assert_called_once_with("groq-fast", "coding")
    weights.record_failure.assert_not_called()


@patch("context_pipeline.routing_weights.get_routing_weights")
def test_record_routing_outcome_failure(mock_get_weights):
    weights = MagicMock()
    mock_get_weights.return_value = weights
    record_routing_outcome("groq-fast", latency_ms=50, success=False, scenario="coding")
    weights.record_failure.assert_called_once_with("groq-fast", "coding")


def test_routing_decision_dataclass_defaults():
    decision = RoutingDecision(backend="test-backend")
    assert decision.strategy == "default"
    assert decision.reflection_notes is None
