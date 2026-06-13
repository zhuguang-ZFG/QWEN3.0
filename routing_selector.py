"""Layer 2: backend selection and ranking (CQ-014 slice 11)."""

from __future__ import annotations

import random
import time

import budget_manager
import route_scorer
import sticky_session

import os

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
    except ImportError:
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
    re,
) -> list[str]:
    """Pin explicit backend first when healthy, budgeted, and selectable."""
    import backends_registry as reg

    if not name or name not in reg.BACKENDS:
        return result
    if re.health_tracker.is_cooled_down(name):
        return result
    if not budget_manager.is_budget_available(name):
        return result
    if health_map.get(name, "healthy") == "dead":
        return result
    state = re.health_tracker.get_backend_state(name)
    if not route_scorer.is_selectable(name, request_type, state):
        return result
    if name not in result:
        return ([name] + result)[:MAX_FALLBACKS]
    return _prioritize(name, result)


def select(request_type: str, health_map: dict,
           sticky_key: str | None = None, scenario: str = "",
           needs_tools: bool = False, recalled_backend: str = "",
           preferred_backend: str = "",
           complexity=None) -> list[str]:
    """从对应池选健康后端，按健康评分排序，过滤预算耗尽，sticky 优先"""
    import routing_engine as re
    import backends_registry as reg

    # Read hierarchical memory for experience-based routing
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        mem_context = hmem.get_context_for_routing("", scenario)
        _preferred = mem_context.get("preferred_backends", []) if isinstance(mem_context, dict) else []
    except Exception:
        _preferred = []

    pool_key = request_type
    if request_type == "chat" and scenario == "coding":
        pool_key = "code"
    elif request_type == "chat" and scenario == "chat":
        pool_key = "chat_fast"

    result = re.router_v3.select_backends(pool_key, health_map)
    result = [b for b in result if not _is_retired(b)]

    if needs_tools:
        result = [b for b in result if "tool_calls" in reg.BACKENDS.get(b, {}).get("caps", [])]
        if len(result) < 8:
            all_capable = [
                n for n, c in reg.BACKENDS.items()
                if "tool_calls" in c.get("caps", [])
                and not re.health_tracker.is_cooled_down(n)
                and budget_manager.is_budget_available(n)
                and not _is_retired(n)
            ]
            for b in all_capable:
                if b not in result:
                    result.append(b)
        # Prioritize backends verified to support native tool calling
        _NATIVE_TOOL_PREFER = {"github", "chinamobile", "ddg", "groq", "cerebras", "longcat"}
        result.sort(key=lambda b: (
            0 if scenario == "coding" and _is_strong_coding_tool_backend(b, reg.BACKENDS.get(b, {})) else 1,
            0 if any(p in b for p in _NATIVE_TOOL_PREFER) else 1,
            reg.BACKENDS.get(b, {}).get("timeout", 30),
        ))

    result = [b for b in result if budget_manager.is_budget_available(b)]

    routing_guard_decisions: dict[str, dict] = {}
    try:
        from observability.routing_guard import backend_guard_snapshot

        guard_snapshot = backend_guard_snapshot()
        raw_decisions = guard_snapshot.get("decisions", {})
        if isinstance(raw_decisions, dict):
            routing_guard_decisions = raw_decisions
            non_quarantined = [
                b for b in result
                if routing_guard_decisions.get(b, {}).get("status") != "quarantined"
            ]
            if non_quarantined:
                result = non_quarantined
    except ImportError:
        routing_guard_decisions = {}

    scores = re.health_tracker.get_scores()
    latency_map = re.health_tracker.get_latency_map()
    health_map = re.health_tracker.get_health_map()

    for b in result:
        base = scores.get(b, 50)

        state = re.health_tracker.get_backend_state(b)
        consec_fails = state.get("consecutive_failures", 0)
        last_success = state.get("last_success", 0)
        avg_lat = latency_map.get(b, 1500)
        health = health_map.get(b, "healthy")

        latency_score = max(0.1, 1.0 - min(avg_lat / 3000, 1.0))
        error_penalty = min(consec_fails * 0.15, 0.9)
        age = time.time() - last_success if last_success else 300
        recency_bonus = max(0, 1.0 - min(age / 60, 1.0))

        if health == "dead":
            scores[b] = 0
        elif health == "degraded":
            scores[b] = base * 0.5 * latency_score * recency_bonus
        else:
            scores[b] = base * latency_score * (1 - error_penalty) * recency_bonus

        try:
            from context_pipeline.routing_weights import get_routing_weights
            rw = get_routing_weights()
            w = rw.get_weight(b, scenario or request_type)
            scores[b] *= w
        except ImportError:
            pass

        # Apply coding quality scores for coding scenarios
        if scenario == "coding":
            try:
                from coding_backend_scorer import get_coding_weight
                scores[b] *= get_coding_weight(b)
            except ImportError:
                pass
            if needs_tools and _is_strong_coding_tool_backend(b, reg.BACKENDS.get(b, {})):
                scores[b] *= 1.25
            pass

        static_latency = _STATIC_LATENCY_ESTIMATE.get(b)
        if static_latency and consec_fails == 0:
            scores[b] += max(0, (2000 - static_latency) / 100)

        guard_decision = routing_guard_decisions.get(b, {})
        if guard_decision:
            try:
                scores[b] *= float(guard_decision.get("penalty_multiplier", 1.0))
            except (TypeError, ValueError):
                scores[b] *= 1.0

        # Hierarchical memory boost for preferred backends
        if b in _preferred:
            scores[b] *= 1.15

    # ML prediction boost — batch apply after per-backend scoring
    try:
        from routing_ml.routing_trainer import get_model, notify_request
        from routing_ml.feature_extractor import extract_features
        _ml_model = get_model()
        if _ml_model and result:
            _features = extract_features(
                [], scenario=scenario, health_map=health_map,
                top_backends=result[:5])
            _topk = _ml_model.predict_topk(_features.features, k=min(5, len(result)))
            for _ml_backend, _ml_score in _topk:
                if _ml_backend in scores:
                    scores[_ml_backend] *= (1.0 + _ml_score * 0.3)  # up to 30% boost
            notify_request()
    except (ImportError, Exception):
        pass

    result.sort(key=lambda b: -(
        scores.get(b, 50) * budget_manager.get_budget_priority(b)
        + random.uniform(0, 3)
    ))

    result = [b for b in result if not re.health_tracker.is_cooled_down(b)]

    try:
        from context_pipeline.signal_extraction import extract_signals, recommend_strategy_from_signals
        from context_pipeline.evolution import apply_strategy_to_backends
        from context_pipeline.event_log import get_request_log
        signals = extract_signals(get_request_log())
        strategy = recommend_strategy_from_signals(signals, backends_available=len(result))
        result = apply_strategy_to_backends(result, strategy, proven_backends=result[:2])
    except ImportError:
        pass
    states = {b: re.health_tracker.get_backend_state(b) for b in result}
    result = [
        b for b in result
        if route_scorer.is_selectable(b, request_type, states.get(b))
    ]
    result = route_scorer.rank_backends(
        result, request_type, scenario,
        health_scores=scores,
        states=states,
        latency_map=re.health_tracker.get_latency_map())

    if sticky_key:
        pinned = sticky_session.get_pinned_backend(sticky_key)
        if (pinned and health_map.get(pinned, "healthy") != "dead"
                and route_scorer.is_selectable(
                    pinned, request_type,
                    re.health_tracker.get_backend_state(pinned))):
            result = _prioritize(pinned, result)
    elif preferred_backend:
        result = _pin_if_selectable(
            preferred_backend, result, health_map, request_type, re,
        )
    elif recalled_backend and recalled_backend in result:
        if (health_map.get(recalled_backend, "healthy") != "dead"
                and route_scorer.is_selectable(
                    recalled_backend, request_type,
                    re.health_tracker.get_backend_state(recalled_backend))):
            result = _prioritize(recalled_backend, result)

    return result[:MAX_FALLBACKS]


def _prioritize(pinned: str, backends: list[str]) -> list[str]:
    """将 pinned 后端排到第一，返回新列表"""
    others = [b for b in backends if b != pinned]
    return [pinned] + others
