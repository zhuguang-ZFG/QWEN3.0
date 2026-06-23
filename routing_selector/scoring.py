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


def _score_latency(avg_lat: float) -> float:
    """Latency component: higher latency yields a lower score."""
    return max(0.1, 1.0 - min(avg_lat / 3000, 1.0))


def _error_penalty(state: dict) -> float:
    """Penalty based on consecutive failures recorded in *state*."""
    consec_fails = state.get("consecutive_failures", 0)
    return min(consec_fails * 0.15, 0.9)


def _apply_routing_weight(score: float, backend: str, scenario: str, request_type: str) -> float:
    """Apply dynamic routing weight if the module is available."""
    try:
        from context_pipeline.routing_weights import get_routing_weights

        return score * get_routing_weights().get_weight(backend, scenario or request_type)
    except ImportError:
        _log.warning("context_pipeline.routing_weights not available; using base score")
        return score


def _apply_coding_adjustments(
    score: float,
    backend: str,
    scenario: str,
    needs_tools: bool,
    backend_meta: dict,
) -> float:
    """Apply coding-specific weight and tool bonus when relevant."""
    if scenario != "coding":
        return score
    try:
        from coding_backend_scorer import get_coding_weight

        score *= get_coding_weight(backend)
    except ImportError:
        _log.warning("coding_backend_scorer not available; skipping coding weight")
    if needs_tools and _is_strong_coding_tool_backend(backend, backend_meta):
        score *= 1.25
    return score


def _apply_static_latency_bonus(score: float, backend: str, consec_fails: int) -> float:
    """Add a small bonus for backends with low static latency and no recent failures."""
    static_latency = _STATIC_LATENCY_ESTIMATE.get(backend)
    if static_latency and consec_fails == 0:
        score += max(0, (2000 - static_latency) / 100)
    return score


def _apply_guard_penalty(score: float, guard_decision: dict) -> float:
    """Apply routing guard penalty multiplier when present."""
    if not guard_decision:
        return score
    try:
        return score * float(guard_decision.get("penalty_multiplier", 1.0))
    except (TypeError, ValueError):
        return score * 1.0


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
    recency_bonus = _score_sticky(backend, state)
    latency_score = _score_latency(latency_map.get(backend, 1500))
    error_penalty = _error_penalty(state)

    if health_factor < 1.0:
        score = base * health_factor * latency_score * recency_bonus
    else:
        score = base * latency_score * (1 - error_penalty) * recency_bonus

    score = _apply_routing_weight(score, backend, scenario, request_type)
    score = _apply_coding_adjustments(
        score, backend, scenario, needs_tools, reg.BACKENDS.get(backend, {})
    )
    score = _apply_static_latency_bonus(score, backend, state.get("consecutive_failures", 0))
    score = _apply_guard_penalty(score, routing_guard_decisions.get(backend, {}))
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
    except (ImportError, Exception) as exc:
        _log.warning("routing_ml boost unavailable: %s", exc)
