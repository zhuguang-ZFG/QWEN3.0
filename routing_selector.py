"""Layer 2: backend selection and ranking (CQ-014 slice 11)."""

from __future__ import annotations

import random
import time

import budget_manager
import health_tracker
import route_scorer
import router_v3
import sticky_session

import logging
import os

_log = logging.getLogger(__name__)

MAX_FALLBACKS = 12

# Static latency estimates (ms) for known fast backends
_STATIC_LATENCY_ESTIMATE = {
    "cerebras_llama8b": 800,
    "cerebras_gptoss": 1200,
    "cerebras_qwen235b": 1500,
    "groq_gptoss_20b": 900,
    "groq_gptoss": 1100,
    "groq_llama8b": 700,
    "groq_llama70b": 1200,
    "groq_llama4": 1000,
    "groq_qwen32b": 1100,
    "github_gpt4o_mini": 1000,
    "github_gpt4o": 1500,
    "mistral_small": 1000,
    "mistral_large": 1500,
    "longcat_chat": 3000,
    "longcat_lite": 2000,
    "scnet_qwen30b": 1200,
    "scnet_qwen235b": 2000,
    "scnet_ds_flash": 1000,
    "scnet_ds_pro": 2500,
}

STRONG_CODING_TOOL_BACKENDS = {
    "dashscope_coding",
    "github_gpt4o_code",
    "mistral_large_code",
    "or_gptoss_120b_code",
    "cfai_qwen_coder_code",
    "scnet_qwen235b_code",
    "scnet_ds_pro_code",
    "ms_qwen35_27b_code",
    "ms_kimi_k25_code",
    "ms_deepseek_v4_code",
    "ms_glm5_code",
}


def _has_valid_key(name: str) -> bool:
    """Check if a backend has a configured, non-empty API key."""
    import backends_registry as reg

    cfg = reg.BACKENDS.get(name, {})
    key = cfg.get("key", "")
    if not key or key in ("none", "YOUR_KEY_HERE", ""):
        return False
    env_var = key if key.startswith("$") else None
    if env_var and not os.environ.get(env_var.lstrip("$"), ""):
        return False
    return True


def _is_retired(name: str) -> bool:
    try:
        import backend_retirement

        return backend_retirement.is_retired(name)
    except ImportError as exc:
        _log.warning("backend_retirement not installed; retirement check disabled: %s", exc)
        return False


def _is_strong_coding_tool_backend(name: str, cfg: dict | None = None) -> bool:
    cfg = cfg or {}
    return (
        name in STRONG_CODING_TOOL_BACKENDS
        or name.endswith("_code")
        or cfg.get("admission") == "code_medium_candidate"
        or cfg.get("private_code_allowed") is True
        or "code" in cfg.get("caps", [])
    )


def _pin_if_selectable(
    name: str,
    result: list[str],
    health_map: dict,
    request_type: str,
) -> list[str]:
    """Pin explicit backend first when healthy, budgeted, and selectable."""
    import backends_registry as reg

    if not name or name not in reg.BACKENDS:
        return result
    if health_tracker.is_cooled_down(name):
        return result
    if not budget_manager.is_budget_available(name):
        return result
    if health_map.get(name, "healthy") == "dead":
        return result
    state = health_tracker.get_backend_state(name)
    if not route_scorer.is_selectable(name, request_type, state):
        return result
    if name not in result:
        return ([name] + result)[:MAX_FALLBACKS]
    return _prioritize(name, result)


_NATIVE_TOOL_PREFER = {"github", "chinamobile", "ddg", "groq", "cerebras", "longcat"}


def _filter_tool_backends(result: list[str], scenario: str) -> list[str]:
    """Filter and rank backends that advertise tool_calls capability."""
    import backends_registry as reg

    result = [b for b in result if "tool_calls" in reg.BACKENDS.get(b, {}).get("caps", [])]
    if len(result) < 8:
        all_capable = [
            n
            for n, c in reg.BACKENDS.items()
            if "tool_calls" in c.get("caps", [])
            and not health_tracker.is_cooled_down(n)
            and budget_manager.is_budget_available(n)
            and not _is_retired(n)
        ]
        for b in all_capable:
            if b not in result:
                result.append(b)
    result.sort(
        key=lambda b: (
            0 if scenario == "coding" and _is_strong_coding_tool_backend(b, reg.BACKENDS.get(b, {})) else 1,
            0 if any(p in b for p in _NATIVE_TOOL_PREFER) else 1,
            reg.BACKENDS.get(b, {}).get("timeout", 30),
        )
    )
    return result


def _build_initial_pool(pool_key: str, health_map: dict, needs_tools: bool, scenario: str) -> list[str]:
    """Select backends from the pool, filter retired/budget/tool constraints."""
    result = router_v3.select_backends(pool_key, health_map)
    result = [b for b in result if not _is_retired(b)]
    if needs_tools:
        result = _filter_tool_backends(result, scenario)
    return [b for b in result if budget_manager.is_budget_available(b)]


def _apply_guard_decisions(result: list[str]) -> tuple[list[str], dict[str, dict]]:
    """Filter quarantined backends and return active decisions."""
    try:
        from observability.routing_guard import backend_guard_snapshot

        raw = backend_guard_snapshot().get("decisions", {})
        decisions = raw if isinstance(raw, dict) else {}
    except ImportError:
        decisions = {}
    non_quarantined = [b for b in result if decisions.get(b, {}).get("status") != "quarantined"]
    return (non_quarantined if non_quarantined else result), decisions


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

    state = health_tracker.get_backend_state(backend)
    consec_fails = state.get("consecutive_failures", 0)
    last_success = state.get("last_success", 0)
    avg_lat = latency_map.get(backend, 1500)
    health = health_map.get(backend, "healthy")
    latency_score = max(0.1, 1.0 - min(avg_lat / 3000, 1.0))
    error_penalty = min(consec_fails * 0.15, 0.9)
    age = time.time() - last_success if last_success else 300
    recency_bonus = max(0, 1.0 - min(age / 60, 1.0))
    if health == "dead":
        score = 0.0
    elif health == "degraded":
        score = base * 0.5 * latency_score * recency_bonus
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


def _rank_backends(result: list[str], scores: dict, request_type: str, scenario: str) -> list[str]:
    """Sort, cool-down filter, selectability filter and rank candidates."""
    result.sort(key=lambda b: -(scores.get(b, 50) * budget_manager.get_budget_priority(b) + random.uniform(0, 3)))
    result = [b for b in result if not health_tracker.is_cooled_down(b)]
    states = {b: health_tracker.get_backend_state(b) for b in result}
    result = [b for b in result if route_scorer.is_selectable(b, request_type, states.get(b))]
    return route_scorer.rank_backends(
        result,
        request_type,
        scenario,
        health_scores=scores,
        states=states,
        latency_map=health_tracker.get_latency_map(),
    )


def _apply_pin(
    result: list[str],
    sticky_key: str | None,
    preferred_backend: str,
    recalled_backend: str,
    health_map: dict,
    request_type: str,
) -> list[str]:
    """Apply sticky/preferred/recalled backend pinning."""
    if sticky_key:
        pinned = sticky_session.get_pinned_backend(sticky_key)
        if (
            pinned
            and health_map.get(pinned, "healthy") != "dead"
            and route_scorer.is_selectable(
                pinned,
                request_type,
                health_tracker.get_backend_state(pinned),
            )
        ):
            return _prioritize(pinned, result)
    if preferred_backend:
        return _pin_if_selectable(preferred_backend, result, health_map, request_type)
    if recalled_backend and recalled_backend in result:
        if health_map.get(recalled_backend, "healthy") != "dead" and route_scorer.is_selectable(
            recalled_backend,
            request_type,
            health_tracker.get_backend_state(recalled_backend),
        ):
            return _prioritize(recalled_backend, result)
    return result


def select(
    request_type: str,
    health_map: dict,
    sticky_key: str | None = None,
    scenario: str = "",
    needs_tools: bool = False,
    recalled_backend: str = "",
    preferred_backend: str = "",
    complexity=None,
) -> list[str]:
    """从对应池选健康后端，按健康评分排序，过滤预算耗尽，sticky 优先"""
    pool_key = request_type
    if request_type == "chat" and scenario == "coding":
        pool_key = "code"
    elif request_type == "chat" and scenario == "chat":
        pool_key = "chat_fast"
    result = _build_initial_pool(pool_key, health_map, needs_tools, scenario)
    result, routing_guard_decisions = _apply_guard_decisions(result)
    scores = health_tracker.get_scores()
    latency_map = health_tracker.get_latency_map()
    health_map = health_tracker.get_health_map()
    _score_backends(
        result, scores, latency_map, health_map, scenario, request_type, needs_tools, routing_guard_decisions
    )
    _apply_ml_boost(result, scores, scenario, request_type, health_map)
    result = _rank_backends(result, scores, request_type, scenario)
    result = _apply_pin(result, sticky_key, preferred_backend, recalled_backend, health_map, request_type)
    return result[:MAX_FALLBACKS]


def _prioritize(pinned: str, backends: list[str]) -> list[str]:
    """将 pinned 后端排到第一，返回新列表"""
    others = [b for b in backends if b != pinned]
    return [pinned] + others
