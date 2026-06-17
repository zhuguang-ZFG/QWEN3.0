"""Routing bridge — records routing outcomes via routing_weights.

Hierarchical memory, reflection, and evolution strategies retired (CP-1/CP-2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    backend: str
    strategy: str = "default"
    confidence: float = 1.0
    reflection_notes: list[str] | None = None


def select_backend_with_evolution(
    backends: list[str],
    scenario: str,
    metrics_snapshot: dict | None = None,
) -> RoutingDecision:
    """Pick first backend; evolution strategy module retired (CP-2)."""
    if not backends:
        return RoutingDecision(backend="none", confidence=0.0)
    return RoutingDecision(backend=backends[0], strategy="fallback")


def reflect_and_adjust(
    backend: str,
    latency_ms: int,
    success: bool,
    scenario: str,
) -> RoutingDecision:
    """Post-route reflection hook (retired; kept for routing_bridge API stability)."""
    return RoutingDecision(backend=backend, strategy="unchanged")


def record_routing_outcome(
    backend: str,
    latency_ms: int,
    success: bool,
    scenario: str,
    skip_weights: bool = False,
) -> None:
    """Record routing outcome into routing weights."""
    if not skip_weights:
        try:
            from context_pipeline.routing_weights import get_routing_weights

            rw = get_routing_weights()
            if success:
                rw.record_success(backend, scenario)
            else:
                rw.record_failure(backend, scenario)
        except Exception as exc:
            _log.debug("routing_weights update failed: %s", exc)


def get_metrics_snapshot() -> dict:
    """Metrics snapshot for evolution (retired)."""
    return {}
