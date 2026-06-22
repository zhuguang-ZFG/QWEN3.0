"""Routing selector scoring helpers."""

from __future__ import annotations

import logging
import time

import health_tracker

from routing_selector.constants import _STATIC_LATENCY_ESTIMATE
from routing_selector.helpers import _is_strong_coding_tool_backend

_log = logging.getLogger(__name__)


def _score_health(backend: str, hmap: dict) -> float:
    """Health component: returns a multiplier based on backend health status."""
    health = hmap.get(backend, "healthy")
    if health == "dead":
        return 0.0
    if health == "degraded":
        return 0.5
    return 1.0


def _score_sticky(backend: str, sticky_map: dict) -> float:
    """Sticky session component: returns a recency multiplier based on last success time."""
    last_success = sticky_map.get("last_success", 0)
    age = time.time() - last_success if last_success else 300
    return max(0, 1.0 - min(age / 60, 1.0))


def _compute_backend_score(
    backend: str,
    base: float,
    latency_map: dict,
    health_map: dict,
    scenario: str,
    request_type: str,
    needs_tools: bool,
    routing_guard_decisions: dict[str, dict],
) -> float:
    """Compute a single backend's health/latency/recency score."""
    import backends_registry as reg

    health_factor = _score_health(backend, health_map)
    if health_factor == 0.0:
        return 0.0

    state = health_tracker.get_backend_state(backend)
    consec_fails = state.get("consecutive_failures", 0)
    error_penalty = min(consec_fails * 0.15, 0.9)
    recency_bonus = _score_sticky(backend, state)

    avg_lat = latency_map.get(backend, 1500)
    latency_score = max(0.1, 1.0 - min(avg_lat / 3000, 1.0))

    if health_factor < 1.0:
        score = base * health_factor * latency_score * recency_bonus
    else:
        score = base * latency_score * (1 - error_penalty) * recency_bonus
    try:
        from context_pipeline.routing_weights import get_routing_weights

        score *= get_routing_weights().get_weight(backend, scenario or request_type)
    except ImportError:
        _log.debug("context_pipeline.routing_weights not available; using base score")
    if scenario == "coding":
        try:
            from coding_backend_scorer import get_coding_weight

            score *= get_coding_weight(backend)
        except ImportError:
            _log.debug("coding_backend_scorer not available; skipping coding weight")
        if needs_tools and _is_strong_coding_tool_backend(backend, reg.BACKENDS.get(backend, {})):
            score *= 1.25
    static_latency = _STATIC_LATENCY_ESTIMATE.get(backend)
    if static_latency and consec_fails == 0:
        score += max(0, (2000 - static_latency) / 100)
    guard_decision = routing_guard_decisions.get(backend, {})
    if guard_decision:
        try:
            score *= float(guard_decision.get("penalty_multiplier", 1.0))
        except (TypeError, ValueError):
            score *= 1.0
    return score


def _score_backends(
    result: list[str],
    scores: dict,
    latency_map: dict,
    health_map: dict,
    scenario: str,
    request_type: str,
    needs_tools: bool,
    routing_guard_decisions: dict[str, dict],
) -> None:
    """Compute and store scores for all candidate backends."""
    for b in result:
        base = scores.get(b, 50)
        scores[b] = _compute_backend_score(
            b,
            base,
            latency_map,
            health_map,
            scenario,
            request_type,
            needs_tools,
            routing_guard_decisions,
        )


def _apply_ml_boost(
    result: list[str],
    scores: dict,
    scenario: str,
    request_type: str,
    health_map: dict,
) -> None:
    """Apply optional ML model boost to top candidate scores."""
    try:
        from routing_ml.routing_trainer import get_model, notify_request
        from routing_ml.feature_extractor import extract_features

        model = get_model()
        if model and result:
            features = extract_features([], scenario=scenario, health_map=health_map, top_backends=result[:5])
            topk = model.predict_topk(features.features, k=min(5, len(result)))
            for ml_backend, ml_score in topk:
                if ml_backend in scores:
                    scores[ml_backend] *= 1.0 + ml_score * 0.3
            notify_request()
    except (ImportError, Exception):
        pass
