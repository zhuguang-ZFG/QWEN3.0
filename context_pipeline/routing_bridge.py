"""Routing bridge — wires evolution, reflection, and memory into routing decisions.

Connects the existing context_pipeline components (evolution strategy selection,
routing reflection, hierarchical memory) to the actual request flow via
route_post_process.py.
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

    try:
        from context_pipeline.evolution import apply_strategy_to_backends, auto_select_strategy
        strategy = auto_select_strategy(metrics_snapshot or {})
        adjusted = apply_strategy_to_backends(strategy, backends, metrics_snapshot or {})
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
    """Apply reflection correction after a routing outcome."""
    try:
        from context_pipeline.reflection import reflect_on_routing
        result = reflect_on_routing(backend, latency_ms, success, scenario)
        corrected = getattr(result, "corrected_backend", None) or str(result)
        was_corrected = getattr(result, "was_corrected", False)
        if was_corrected and corrected != backend:
            _log.info("reflection adjusted: %s -> %s", backend, corrected)
            return RoutingDecision(
                backend=corrected,
                strategy="reflection_correction",
                confidence=0.8,
                reflection_notes=[f"corrected {backend} -> {corrected}"],
            )
    except ImportError:
        _log.debug("reflection module not available")
    except Exception as exc:
        _log.debug("reflection failed: %s", exc)

    return RoutingDecision(backend=backend, strategy="unchanged")


def record_routing_outcome(
    backend: str,
    latency_ms: int,
    success: bool,
    scenario: str,
) -> None:
    """Record routing outcome into hierarchical memory and routing weights."""
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        hmem.update_performance(backend, latency_ms, success)
    except Exception as exc:
        _log.debug("hierarchical_memory update failed: %s", exc)

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
    """Collect metrics from hierarchical memory for evolution strategy."""
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        perf_entries = hmem.L1.search("perf:")
        return {
            "backends": {
                k.replace("perf:", ""): v
                for k, v in perf_entries
            }
        }
    except Exception as exc:
        _log.warning("operation failed: %s", exc)
        return {}
