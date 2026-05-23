"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现
"""

import json
import time
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

import router_v3
import health_tracker
import sticky_session
import budget_manager
import route_scorer
import speculative
import identity_guard
import skills_injector as skills_mod
import semantic_cache
from response_builder import build_response, build_anthropic_response, make_chat_id

MAX_FALLBACKS = 5


@dataclass
class RouteResult:
    backend: str = ""
    answer: str = ""
    request_type: str = "chat"
    scenario: str = ""
    ms: int = 0
    fallback_used: bool = False
    skills_injected: list = field(default_factory=list)
    retrieval_context: str = ""


# ─── Layer 1: 分类 ───────────────────────────────────────────────────────────

def classify(query: str, messages: list[dict], *,
             fmt: str = "openai", ide_source: str = "",
             system_prompt: str = "", headers: dict = None) -> str:
    """判断请求类型: ide / chat / vision / image"""
    headers = headers or {}

    if fmt == "anthropic":
        return "ide"

    if ide_source and ide_source in router_v3.IDE_SOURCES:
        return "ide"

    ua = headers.get("user-agent", "").lower()
    if any(x in ua for x in ["claude-code", "cursor", "aider", "codex", "cline", "continue", "vscode", "kiro", "zed", "trae", "windsurf", "copilot"]):
        return "ide"

    if system_prompt and router_v3.detect_ide_from_system_prompt(system_prompt):
        return "ide"

    if _has_image_blocks(messages):
        return "vision"

    return "chat"


def classify_scenario(query: str, messages: list[dict], *,
                      ide_source: str = "", request_type: str = "") -> str:
    """判断场景: coding / chat。决定走质量路径还是速度路径。"""
    if request_type == "ide":
        return "coding"
    if ide_source and ide_source.lower() in (
        "claude code", "cursor", "aider", "cline", "codex",
        "continue", "vscode", "vs code",
    ):
        return "coding"

    last_content = ""
    if messages:
        last = messages[-1]
        last_content = last.get("content", "") if isinstance(last, dict) else ""
        if isinstance(last_content, list):
            last_content = " ".join(
                b.get("text", "") for b in last_content if isinstance(b, dict))

    text = last_content or query

    if "```" in text:
        return "coding"
    if any(kw in text for kw in ("Traceback", "Error:", "TypeError", "SyntaxError")):
        return "coding"

    code_signals = ("def ", "class ", "import ", "function ", "const ", "async ",
                    "return ", "if __name__", "from ", "export ")
    if sum(1 for s in code_signals if s in text) >= 2:
        return "coding"

    return "chat"


def _has_image_blocks(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content", []) if isinstance(m, dict) else []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False


# ─── Layer 2: 选择 ───────────────────────────────────────────────────────────

def select(request_type: str, health_map: dict,
           sticky_key: str = None, scenario: str = "") -> list[str]:
    """从对应池选健康后端，按健康评分排序，过滤预算耗尽，sticky 优先"""
    pool_key = request_type
    if request_type == "chat" and scenario == "coding":
        pool_key = "code"
    elif request_type == "chat" and scenario == "chat":
        pool_key = "chat_fast"

    result = router_v3.select_backends(pool_key, health_map)

    # 过滤预算耗尽的后端
    result = [b for b in result if budget_manager.is_budget_available(b)]

    # 按健康评分排序（高分优先，带随机扰动避免羊群效应）
    # 预算接近耗尽的后端降权
    scores = health_tracker.get_scores()
    if scores:
        # ── Integration: Routing Weights (Phase 15) ───────────────────────
        try:
            from context_pipeline.routing_weights import get_routing_weights
            rw = get_routing_weights()
            for b in result:
                w = rw.get_weight(b, scenario or request_type)
                scores[b] = scores.get(b, 50) * w
        except ImportError:
            pass

        result.sort(key=lambda b: -(
            scores.get(b, 50) * budget_manager.get_budget_priority(b)
            + random.uniform(0, 8)
        ))

    result = [b for b in result if not health_tracker.is_cooled_down(b)]

    # ── Integration: Evolution Strategy (Phase 18) ────────────────────────
    try:
        from context_pipeline.signal_extraction import extract_signals, recommend_strategy_from_signals
        from context_pipeline.evolution import apply_strategy_to_backends
        from context_pipeline.event_log import get_request_log
        signals = extract_signals(get_request_log())
        strategy = recommend_strategy_from_signals(signals, backends_available=len(result))
        result = apply_strategy_to_backends(result, strategy, proven_backends=result[:2])
    except ImportError:
        pass
    states = {b: health_tracker.get_backend_state(b) for b in result}
    result = [
        b for b in result
        if route_scorer.is_selectable(b, request_type, states.get(b))
    ]
    result = route_scorer.rank_backends(
        result, request_type, scenario,
        health_scores=scores,
        states=states,
        latency_map=health_tracker.get_latency_map())

    if sticky_key:
        pinned = sticky_session.get_pinned_backend(sticky_key)
        if (pinned and health_map.get(pinned, "healthy") != "dead"
                and route_scorer.is_selectable(
                    pinned, request_type,
                    health_tracker.get_backend_state(pinned))):
            result = _prioritize(pinned, result)

    return result[:MAX_FALLBACKS]


def _prioritize(pinned: str, backends: list[str]) -> list[str]:
    """将 pinned 后端排到第一，返回新列表"""
    others = [b for b in backends if b != pinned]
    return [pinned] + others


# ─── Layer 3: Skills 注入 ────────────────────────────────────────────────────

def inject_skills(messages: list[dict], *,
                  backend: str = "", ide_source: str = "",
                  system_prompt: str = "") -> list[dict]:
    """根据后端能力和 IDE 注入 skills"""
    return skills_mod.apply_skills(
        backend=backend, messages=messages,
        system_prompt=system_prompt, ide_source=ide_source)


# ─── Layer 4: 执行 ───────────────────────────────────────────────────────────

def execute(backends: list[str],
            call_fn: Callable[[str, list[dict], int], str],
            messages: list[dict],
            max_tokens: int = 4096) -> tuple[str, str, int]:
    """按序尝试后端，失败则 fallback。返回 (backend, answer, error_count)"""
    t0 = time.time()
    errors = 0
    tried_any = False

    for backend in backends[:MAX_FALLBACKS]:
        if health_tracker.is_cooled_down(backend):
            errors += 1
            continue
        tried_any = True
        try:
            t_backend = time.time()
            answer = call_fn(backend, messages, max_tokens)
            if answer and len(answer.strip()) > 5:
                latency_ms = (time.time() - t_backend) * 1000
                health_tracker.record_success(backend, latency_ms)
                budget_manager.record_usage(backend)
                return backend, answer, errors
            else:
                health_tracker.record_failure(backend, error_code=None)
                errors += 1
        except Exception as e:
            code = _extract_code(e)
            if code != 503:
                health_tracker.record_failure(backend, error_code=code)
            errors += 1

    # 全部冷却时强制试前3个，绝不空手而归
    if not tried_any:
        health_tracker.detect_and_reset_mass_failure()
        for backend in backends[:3]:
            try:
                answer = call_fn(backend, messages, max_tokens)
                if answer and len(answer.strip()) > 5:
                    health_tracker.record_success(backend, (time.time() - t0) * 1000)
                    return backend, answer, errors
            except Exception as e:
                import logging
                logging.warning(f"[EXECUTE] force-try {backend} failed: {type(e).__name__}: {e}")
                health_tracker.record_failure(backend, error_code=_extract_code(e))
                errors += 1

    # 批量熔断检测 + 直连保底
    if health_tracker.detect_and_reset_mass_failure():
        for b in router_v3.DIRECT_BACKENDS[:2]:
            if health_tracker.is_cooled_down(b):
                continue
            try:
                answer = call_fn(b, messages, max_tokens)
                if answer and len(answer.strip()) > 5:
                    return b, answer, errors
            except Exception as e:
                health_tracker.record_failure(b, error_code=_extract_code(e))
                errors += 1

    return "exhausted", "", errors


def _extract_code(e: Exception) -> Optional[int]:
    for attr in ("status_code", "code", "status"):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            return val
    s = str(e)
    if "429" in s:
        return 429
    if "401" in s:
        return 401
    if "403" in s:
        return 403
    return None


# ─── Layer 5: 响应 ───────────────────────────────────────────────────────────

def respond(result: RouteResult, fmt: str = "openai",
            model: str = "lima-1.3") -> dict:
    chat_id = make_chat_id()
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, result.answer, result.backend, model)
    resp = build_response(chat_id, result.answer, result.backend, result.ms)
    resp["x_lima_meta"]["request_type"] = result.request_type
    resp["x_lima_meta"]["skills_injected"] = result.skills_injected
    return resp


# ─── 主入口 ─────────────────────────────────────────────────────────────────

def route(query: str, messages: list[dict], *,
          fmt: str = "openai", ide_source: str = "",
          model: str = "", max_tokens: int = 4096,
          system_prompt: str = "", headers: dict = None,
          call_fn: Callable = None,
          cache_enabled: bool = True) -> RouteResult:
    """统一路由入口。call_fn(backend, messages, max_tokens) -> str"""
    t0 = time.time()

    # 缓存检查 (仅 temperature=0 的确定性请求)
    if cache_enabled:
        cached = semantic_cache.get(model or "default", messages)
        if cached:
            ms = int((time.time() - t0) * 1000)
            return RouteResult(backend="cache", answer=cached,
                               request_type="cache_hit", ms=ms)

    # 身份/能力问题拦截（不走后端，不消耗配额）
    identity_answer = identity_guard.detect_identity_question(query)
    if identity_answer:
        ms = int((time.time() - t0) * 1000)
        return RouteResult(backend="identity_guard", answer=identity_answer,
                           request_type="identity", ms=ms)

    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source,
                        system_prompt=system_prompt, headers=headers)

    scenario = classify_scenario(query, messages,
                                 ide_source=ide_source, request_type=req_type)

    # ── Integration: Skill Store recall (Phase 17) ────────────────────────
    _skill = None
    try:
        from context_pipeline.skill_store import get_skill_store
        _skill = get_skill_store().recall(messages, scenario)
    except ImportError:
        pass

    # ── Integration: Entity Extraction (Phase 23) ─────────────────────────
    messages, _retrieval_text = inject_retrieval_context(messages)

    # ── Integration: Graph Retrieval + Reranking (Phase 24/25) ────────────

    # ── Integration: Retrieval Injection (Phase 26) ──────────────────────
    # ── Integration: Complexity Assessment (Phase 14) ─────────────────────
    try:
        from context_pipeline.complexity import assess_complexity, decide_topology
        raw_msgs = [{"role": m.get("role", ""), "content": m.get("content", "")} if isinstance(m, dict) else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")} for m in messages]
        _complexity_score = assess_complexity(raw_msgs, ide_source=ide_source)
        _topology = decide_topology(_complexity_score)
    except ImportError:
        _topology = None

    # ── Code Orchestrator: 编程场景走强模型带动弱模型 pipeline ──
    if scenario == "coding" and call_fn:
        try:
            import code_orchestrator
            orch_result = code_orchestrator.handle(
                query, messages, call_fn, max_tokens)
            if orch_result.get("answer"):
                ms = int((time.time() - t0) * 1000)
                return RouteResult(
                    backend=orch_result["backend"],
                    answer=orch_result["answer"],
                    request_type=f"code_{orch_result['tier']}",
                    ms=ms, scenario=scenario,
                    retrieval_context=_retrieval_text)
        except Exception as e:
            import logging as _logging
            _logging.warning(f"[ORCH] code_orchestrator failed: {type(e).__name__}: {e}")

    sticky_key = sticky_session.compute_key(
        model or "default",
        json.dumps(messages, ensure_ascii=False))

    hmap = health_tracker.get_health_map()
    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario)

    messages_injected = inject_skills(
        messages, backend=backends[0] if backends else "",
        ide_source=ide_source, system_prompt=system_prompt)

    injected_ids = _get_injected_ids(messages, messages_injected)

    if call_fn:
        # 根据复杂度选择执行策略
        complexity = speculative.classify_complexity(query, messages)

        if complexity == "simple" and req_type in ("ide", "chat"):
            # 简单问题：并行投机执行（5个快速后端竞速，5秒超时）
            affinity_backends = speculative.get_affinity_backends("simple")
            spec_candidates = [b for b in affinity_backends
                               if not health_tracker.is_cooled_down(b)
                               and budget_manager.is_budget_available(b)
                               and speculative.is_historically_fast(b)]
            if len(spec_candidates) >= 2:
                try:
                    final_backend, answer, _ = speculative.speculative_call(
                        spec_candidates, call_fn, messages_injected, max_tokens,
                        max_parallel=5, timeout_sec=5.0)
                except RuntimeError:
                    final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens)
            else:
                final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens)
        elif complexity == "code":
            # 代码问题：优先走代码专用后端
            code_backends = speculative.get_affinity_backends("code")
            code_available = [b for b in code_backends
                              if not health_tracker.is_cooled_down(b)
                              and budget_manager.is_budget_available(b)]
            merged = code_available + [b for b in backends if b not in code_available]
            final_backend, answer, _ = execute(merged, call_fn, messages_injected, max_tokens)
        else:
            # 复杂问题 / vision：走 premium 后端，顺序执行
            final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens)

        if final_backend != "exhausted":
            sticky_session.pin_backend(sticky_key, final_backend)
            if cache_enabled and answer:
                semantic_cache.put(model or "default", messages, 0, answer)
    else:
        final_backend, answer = backends[0] if backends else "none", ""

    ms = int((time.time() - t0) * 1000)

    # ── Integration: Narrative Casting (Phase 12) — on fallback ────────────
    _fallback_used = (final_backend not in ("exhausted", "none") and backends and final_backend != backends[0])
    if _fallback_used and answer:
        try:
            from context_pipeline.narrative import reframe_for_handoff
            reframe_for_handoff(messages_injected, backends[0], final_backend)
        except (ImportError, Exception):
            pass

    # ── Integration: Hierarchical Memory L1 (Phase 16) ────────────────────
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        hmem.update_performance(final_backend, ms, bool(answer))
        hmem.set_global_fact(f"last_scenario:{scenario}", final_backend)
    except ImportError:
        pass

    # ── Integration: Response Pipeline + Signal Extraction (Phase 9/15/17/20) ──
    try:
        from context_pipeline.response_processors import build_default_response_pipeline
        from context_pipeline.response_pipeline import ResponseContext
        resp_ctx = build_default_response_pipeline().process(ResponseContext(
            backend=final_backend, response_text=answer or "",
            latency_ms=ms, status_code=200 if answer else 500,
        ))
        # Phase 15: Update routing weights based on success/failure
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if resp_ctx.quality_ok and final_backend not in ("exhausted", "none", "cache"):
            rw.record_success(final_backend, scenario)
        elif final_backend not in ("exhausted", "none", "cache"):
            rw.record_failure(final_backend, scenario)
        # Phase 17: Crystallize successful routing as skill
        if resp_ctx.quality_ok and answer and final_backend not in ("exhausted", "none", "cache"):
            from context_pipeline.skill_store import get_skill_store
            get_skill_store().crystallize(messages, scenario, final_backend, 0, ms)
    except ImportError:
        pass

    return RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, scenario=scenario, ms=ms,
        fallback_used=(final_backend not in ("exhausted", "none") and backends and final_backend != backends[0]),
        skills_injected=injected_ids,
        retrieval_context=_retrieval_text,
    )


def _get_injected_ids(original: list[dict], modified: list[dict]) -> list[str]:
    """提取被注入的 skill ID"""
    if len(modified) <= len(original):
        return []
    for msg in modified:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if "Available skills:" in content:
                names = content.replace("Available skills:", "").strip()
                return ["dir:" + n.strip() for n in names.split(",") if n.strip()]
    extra = len(modified) - len(original)
    return [f"injected_{extra}_skills"] if extra > 0 else []


def inject_retrieval_context(messages: list[dict]) -> tuple[list[dict], str]:
    """Extract entities, run graph retrieval, and inject formatted context into messages.

    Returns (messages_with_context, retrieval_text).
    Safe to call from any path — returns original messages unchanged on failure.
    """
    try:
        from context_pipeline.entity_extraction import extract_entities
        from context_pipeline.code_scanner import get_code_graph
        from context_pipeline.graph_retrieval import dual_layer_search, RetrievalResult
        from context_pipeline.reranking import rerank_results, format_for_injection
    except ImportError:
        return messages, ""

    try:
        raw_msgs = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            if isinstance(m, dict) else
            {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
            for m in messages
        ]
        entities = extract_entities(raw_msgs)
        terms = entities.to_query_terms()
        if not terms:
            return messages, ""

        graph = get_code_graph()
        vector_results = [RetrievalResult(path=e, score=0.7, source="vector") for e in terms[:5]]
        merged = dual_layer_search(terms, vector_results, graph, max_results=8)
        reranked = rerank_results(merged, terms, top_k=5)
        if not reranked:
            return messages, ""

        text = format_for_injection(reranked)
        if not text:
            return messages, ""

        retrieval_msg = {"role": "system", "content": text}
        result = list(messages)
        if result and result[0].get("role") == "system":
            result.insert(1, retrieval_msg)
        else:
            result.insert(0, retrieval_msg)

        from context_pipeline.retrieval_trace import record_trace, RetrievalTrace
        record_trace(RetrievalTrace(
            query_entities=terms,
            candidates_searched=len(merged),
            reranked_results=[
                {"path": r.path, "score": round(r.score, 2), "source": r.source}
                for r in reranked
            ],
            injected_text=text,
            injected_chars=len(text),
        ))
        return result, text
    except Exception:
        return messages, ""
