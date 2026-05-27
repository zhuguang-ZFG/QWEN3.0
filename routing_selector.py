"""Layer 2: backend selection and ranking (CQ-014 slice 11)."""

from __future__ import annotations

import random

import budget_manager
import route_scorer
import sticky_session

MAX_FALLBACKS = 5

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
}


def select(request_type: str, health_map: dict,
           sticky_key: str = None, scenario: str = "",
           needs_tools: bool = False) -> list[str]:
    """从对应池选健康后端，按健康评分排序，过滤预算耗尽，sticky 优先"""
    import routing_engine as re
    import backends_registry as reg

    pool_key = request_type
    if request_type == "chat" and scenario == "coding":
        pool_key = "code"
    elif request_type == "chat" and scenario == "chat":
        pool_key = "chat_fast"

    result = re.router_v3.select_backends(pool_key, health_map)

    if needs_tools:
        result = [b for b in result if "tool_calls" in reg.BACKENDS.get(b, {}).get("caps", [])]
        if not result:
            code_pool = re.router_v3.select_backends("code", health_map)
            result = [b for b in code_pool if "tool_calls" in reg.BACKENDS.get(b, {}).get("caps", [])]

    result = [b for b in result if budget_manager.is_budget_available(b)]

    scores = re.health_tracker.get_scores()
    if scores:
        try:
            from context_pipeline.routing_weights import get_routing_weights
            rw = get_routing_weights()
            for b in result:
                w = rw.get_weight(b, scenario or request_type)
                scores[b] = scores.get(b, 50) * w
        except ImportError:
            pass

        try:
            from context_pipeline.hierarchical_memory import get_hierarchical_memory
            hmem = get_hierarchical_memory()
            for b in result:
                perf = hmem.L1.get(f"perf:{b}")
                if perf and perf.get("total", 0) >= 3:
                    success_rate = perf.get("success_rate", 0.5)
                    latency_bonus = max(0, (2000 - perf.get("avg_latency", 1000)) / 100)
                    scores[b] = scores.get(b, 50) * (0.7 + 0.3 * success_rate) + latency_bonus
                else:
                    static_latency = _STATIC_LATENCY_ESTIMATE.get(b, 1500)
                    scores[b] = scores.get(b, 50) + max(0, (2000 - static_latency) / 100)
        except Exception:
            pass

        result.sort(key=lambda b: -(
            scores.get(b, 50) * budget_manager.get_budget_priority(b)
            + random.uniform(0, 8)
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

    return result[:MAX_FALLBACKS]


def _prioritize(pinned: str, backends: list[str]) -> list[str]:
    """将 pinned 后端排到第一，返回新列表"""
    others = [b for b in backends if b != pinned]
    return [pinned] + others
