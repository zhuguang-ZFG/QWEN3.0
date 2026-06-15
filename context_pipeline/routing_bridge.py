"""Routing bridge — wires evolution strategy and routing weights into routing decisions.

Connects context_pipeline evolution (optional) and routing_weights to
route_post_process.py. Hierarchical memory / reflection retired (CP-1).
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
    """Select backend using evolution strategy based on recent metrics."""
    if not backends:
        return RoutingDecision(backend="none", confidence=0.0)
    if not metrics_snapshot:
        return RoutingDecision(backend=backends[0], strategy="fallback")

    try:
        from context_pipeline.evolution import auto_select_strategy, apply_strategy_to_backends
        recent_error_rate = float(metrics_snapshot.get("recent_error_rate", 0.0))
        recent_fallback_rate = float(metrics_snapshot.get("recent_fallback_rate", 0.0))
        backends_available = int(metrics_snapshot.get("backends_available", len(backends)))
        raw_proven = metrics_snapshot.get("proven_backends")
        proven_backends = raw_proven if isinstance(raw_proven, list) else None
        strategy = auto_select_strategy(
            recent_error_rate,
            recent_fallback_rate,
            backends_available,
        )
        adjusted = apply_strategy_to_backends(backends, strategy, proven_backends)
        if adjusted:
            return RoutingDecision(
                backend=adjusted[0],
                strategy=strategy.value if hasattr(strategy, "value") else str(strategy),
                confidence=0.9,
            )
    except ImportError:
        _log.debug("evolution module not available")
    except Exception as exc:
        _log.debug("evolution selection failed: %s", exc)

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
    """Collect metrics for evolution strategy (hierarchical memory retired)."""
    return {}
