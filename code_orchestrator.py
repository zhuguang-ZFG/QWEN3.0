"""
code_orchestrator.py — 编程模型塔 V3：上下文工程+容错+自愈+学习
Pipeline: Context Engineering → Intent Amplify → Multi-Pass Refine → Quality Gate → Repair

增强功能:
  - 集成 multi_pass_refiner: Generate→Review→Fix→Verify 四遍精炼
  - 集成 opencode_tool_aware: 工具感知提示注入
  - 精确语法错误修复注入
"""
from __future__ import annotations

import logging
import time

import backend_reputation
import health_tracker
import quality_gate
import route_scorer
import runtime_topology
from code_orchestrator_context import (
    LATENCY_BUDGET,
    MAX_REPAIR_ATTEMPTS,
    POOLS,
    build_enhanced_query,
    build_system_prompt,
    classify_code_tier,
    detect_language,
    enhance_context,
    get_stats,
    record_streaming_quality,
)

logger = logging.getLogger(__name__)

# Back-compat re-exports (tests and adapters import from this module)
__all__ = [
    "POOLS",
    "LATENCY_BUDGET",
    "MAX_REPAIR_ATTEMPTS",
    "detect_language",
    "classify_code_tier",
    "handle",
    "enhance_context",
    "record_streaming_quality",
    "get_stats",
]


def handle(query: str, messages: list, call_fn, max_tokens: int = 4096,
           ide_source: str = "") -> dict:
    """编程模型塔主入口。返回 {answer, backend, tier, repaired, score}。

    集成 multi_pass_refiner 作为核心执行策略：
      - Generate→Review→Fix→Verify 四遍精炼
      - 若 multi_pass 不可用，回退到原有单遍执行
    """
    tier = classify_code_tier(query, messages)
    budget = LATENCY_BUDGET[tier]
    t0 = time.time()

    system = build_system_prompt(query, messages)
    enhanced_query = build_enhanced_query(query)

    # ── Try multi-pass refinement first (for standard/complex tiers) ──
    if tier in ("standard", "complex"):
        try:
            import multi_pass_refiner
            mp_result = multi_pass_refiner.refine(
                enhanced_query, messages, call_fn,
                max_tokens=max_tokens, system_prompt=system,
                ide_source=ide_source,
            )
            if mp_result.get("answer") and mp_result.get("passes", 0) > 0:
                logger.info(
                    "[ORCH] multi_pass success: %d passes, score=%d, "
                    "backend=%s, %.0fms",
                    mp_result["passes"], mp_result.get("score", 0),
                    mp_result.get("backend", "?"), mp_result.get("latency_ms", 0),
                )
                return {
                    "answer": mp_result["answer"],
                    "backend": mp_result["backend"],
                    "tier": tier,
                    "repaired": mp_result.get("fixed", False),
                    "score": mp_result.get("score", 70),
                }
            logger.debug(
                "[ORCH] multi_pass skipped/empty: %s",
                mp_result.get("skipped", "empty_answer"),
            )
        except (ImportError, Exception) as e:
            logger.debug("[ORCH] multi_pass_refiner unavailable: %s", type(e).__name__)

    # ── Fallback to original single-pass execution ──
    if tier == "simple":
        result = _execute_simple(enhanced_query, messages, call_fn, system, max_tokens, t0, budget)
    elif tier == "standard":
        result = _execute_standard(enhanced_query, messages, call_fn, system, max_tokens, t0, budget)
    else:
        result = _execute_complex(enhanced_query, messages, call_fn, system, max_tokens, t0, budget)

    if result.get("backend") and result["backend"] != "exhausted":
        passed = result.get("score", 70) >= 70
        backend_reputation.record(result["backend"], passed, f"code_{tier}")

    return result


def _backend_selectable(name: str) -> bool:
    if health_tracker.is_cooled_down(name):
        return False
    state = health_tracker.get_backend_state(name)
    return route_scorer.is_selectable(name, "ide", state)


def _try_backends_ranked(pool_name: str, messages: list, call_fn,
                         system: str, max_tokens: int,
                         t0: float, deadline: float) -> tuple[str, str]:
    pool = runtime_topology.filter_backends(POOLS.get(pool_name, []))
    ranked = [
        b for b in backend_reputation.sort_by_reputation(pool)
        if _backend_selectable(b)
    ]
    for backend in ranked:
        if time.time() - t0 > deadline:
            break
        try:
            msgs = messages.copy()
            if system:
                msgs.insert(0, {"role": "system", "content": system})
            answer = call_fn(backend, msgs, max_tokens)
            if answer and len(answer.strip()) > 5:
                return backend, answer
        except Exception as exc:
            logger.warning("code_orchestrator backend %s failed: %s", backend, exc)
            continue
    return "", ""


def _execute_simple(query, messages, call_fn, system, max_tokens, t0, budget):
    msgs = _build_msgs(query, messages)
    backend, answer = _try_backends_ranked("fast", msgs, call_fn, system, max_tokens, t0, budget)
    if not answer:
        backend, answer = _try_backends_ranked("coder", msgs, call_fn, system, max_tokens, t0, budget)
    return {"answer": answer, "backend": backend, "tier": "simple",
            "repaired": False, "score": 80 if answer else 0}


def _execute_standard(query, messages, call_fn, system, max_tokens, t0, budget):
    msgs = _build_msgs(query, messages)
    backend, answer = _try_backends_ranked("coder", msgs, call_fn, system, max_tokens, t0, budget * 0.5)
    if not answer:
        return {"answer": "", "backend": "exhausted", "tier": "standard",
                "repaired": False, "score": 0}

    gate = quality_gate.check(answer, query)
    if gate["passed"]:
        backend_reputation.record(backend, True, "code_standard")
        return {"answer": answer, "backend": backend, "tier": "standard",
                "repaired": False, "score": gate["score"]}

    backend_reputation.record(backend, False, "code_standard")
    remaining = budget - (time.time() - t0)
    if remaining < 3.0:
        return {"answer": answer, "backend": backend, "tier": "standard",
                "repaired": False, "score": gate["score"]}

    repaired = _repair_with_breaker(query, answer, gate["reasons"],
                                     msgs, call_fn, system, max_tokens, t0, budget)
    if repaired:
        return {"answer": repaired[1], "backend": repaired[0], "tier": "standard",
                "repaired": True, "score": repaired[2]}

    return {"answer": answer, "backend": backend, "tier": "standard",
            "repaired": False, "score": gate["score"]}


def _execute_complex(query, messages, call_fn, system, max_tokens, t0, budget):
    msgs = _build_msgs(query, messages)

    backend, answer = _try_backends_ranked("strong", msgs, call_fn, system, max_tokens, t0, budget * 0.7)
    if answer:
        gate = quality_gate.check(answer, query)
        if gate["passed"]:
            backend_reputation.record(backend, True, "code_complex")
            return {"answer": answer, "backend": backend, "tier": "complex",
                    "repaired": False, "score": gate["score"]}
        backend_reputation.record(backend, False, "code_complex")

    remaining = budget - (time.time() - t0)
    if remaining > 3.0:
        backend, answer = _try_backends_ranked("coder", msgs, call_fn, system, max_tokens, t0, budget)
        if answer:
            return {"answer": answer, "backend": backend, "tier": "complex",
                    "repaired": False, "score": quality_gate.check(answer, query)["score"]}

    return {"answer": answer or "", "backend": backend or "exhausted",
            "tier": "complex", "repaired": False, "score": 0}


def _repair_with_breaker(query, bad_answer, reasons, messages,
                          call_fn, system, max_tokens, t0, budget):
    """Repair a bad coding answer with different backends.

    Enhanced: extracts precise syntax error info from quality_gate reasons
    to give the repair model exact line numbers and error messages.
    """
    strong_pool = POOLS["strong"][:]

    # Extract precise syntax error details for targeted repair
    syntax_detail = ""
    for reason in reasons:
        if "python_syntax_error:" in reason:
            # Extract the error detail part after the colon
            detail = reason.split(":", 1)[-1] if ":" in reason else ""
            if detail:
                syntax_detail = f"\nSyntax errors found:\n  {detail}\n"
            break

    for attempt in range(MAX_REPAIR_ATTEMPTS):
        remaining = budget - (time.time() - t0)
        if remaining < 2.0 or not strong_pool:
            break

        backend_to_use = strong_pool.pop(0)

        if attempt == 0:
            # Build precise repair prompt with error details
            repair_parts = [f"以下代码回复存在问题: {', '.join(reasons)}"]
            if syntax_detail:
                repair_parts.append(syntax_detail)
            repair_parts.append(f"原始问题: {query}")
            repair_parts.append(f"有问题的回复:\n{bad_answer[:1500]}")
            repair_parts.append("请修复上述问题，直接给出正确的完整代码回复。")
            repair_prompt = "\n\n".join(repair_parts)
        else:
            repair_prompt = query

        repair_msgs = [{"role": "user", "content": repair_prompt}]
        try:
            msgs = repair_msgs.copy()
            if system:
                msgs.insert(0, {"role": "system", "content": system})
            answer = call_fn(backend_to_use, msgs, max_tokens)
            if answer and len(answer.strip()) > 10:
                gate = quality_gate.check(answer, query)
                if gate["passed"]:
                    backend_reputation.record(backend_to_use, True, "code_repair")
                    return (backend_to_use, answer, gate["score"])
                backend_reputation.record(backend_to_use, False, "code_repair")
        except Exception as exc:
            logger.debug(
                "code_orchestrator repair attempt failed backend=%s: %s",
                backend_to_use,
                type(exc).__name__,
            )
            continue

    return None


def _build_msgs(query, messages):
    if len(messages) > 1:
        return messages[:-1] + [{"role": "user", "content": query}]
    return [{"role": "user", "content": query}]
