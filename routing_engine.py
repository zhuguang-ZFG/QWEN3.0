"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现
"""

import json
import logging
import time
from collections.abc import Callable

import budget_manager
import health_tracker
import identity_guard
import router_v3
import semantic_cache
import speculative
import sticky_session
from context_pipeline.retrieval_injection import inject_retrieval_context
from model_resolver import resolve_backend
from response_cleaner import clean_response
from routing_classifier import classify, classify_agent_task, classify_scenario
from routing_engine_context import inject_all_context
from routing_engine_context import inject_all_context as prepare_route_context
from routing_engine_opencode import try_code_orchestration
from routing_engine_postprocess import finalize_route
from routing_engine_response import respond
from routing_engine_skills import apply_backend_aware_skills, inject_skills
from routing_engine_skills import get_injected_ids as _get_injected_ids
from routing_engine_types import RouteResult
from routing_executor import execute
from routing_selector import select

_log = logging.getLogger(__name__)
# Re-export for backward compatibility
__all__ = [
    "RouteResult",
    "classify",
    "classify_scenario",
    "select",
    "inject_skills",
    "execute",
    "respond",
    "route",
]

def route(query: str, messages: list[dict], *,
          fmt: str = "openai", ide_source: str = "",
          model: str = "", max_tokens: int = 4096,
          system_prompt: str = "", headers: dict | None = None,
          call_fn: Callable | None = None,
          cache_enabled: bool = True,
          channel_role: str = "default",
          needs_tools: bool = False,
          tools: list[dict] | None = None,
          client_ip: str = "",
          user_agent: str = "") -> RouteResult:
    """统一路由入口。call_fn(backend, messages, max_tokens) -> str"""
    t0 = time.time()

    identity_answer = identity_guard.detect_identity_question(
        query, channel_role=channel_role)
    if identity_answer:
        ms = int((time.time() - t0) * 1000)
        return RouteResult(backend="identity_guard", answer=identity_answer,
                           request_type="identity", ms=ms)

    if cache_enabled:
        cached = semantic_cache.get(model or "default", messages)
        if cached:
            cleaned = clean_response(cached, "cache")
            answer = cleaned if cleaned else cached
            ms = int((time.time() - t0) * 1000)
            try:
                from integrations.cloud_services import log_routing_decision
                log_routing_decision("cache", "cache_hit", "", ms)
            except Exception as e:
                logging.warning("routing_engine: cache logging failed: %s", e)
            return RouteResult(backend="cache", answer=answer,
                               request_type="cache_hit", ms=ms)

    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source,
                        system_prompt=system_prompt, headers=headers or {})

    scenario = classify_scenario(query, messages,
                                 ide_source=ide_source, request_type=req_type)

    # ── Agent task detection (Mode 3: Hermes Agent routing) ──
    needs_agent = classify_agent_task(
        query, messages, ide_source=ide_source, system_prompt=system_prompt)
    if needs_agent:
        logging.info("routing_engine: agent task detected, routing to hermes_agent pipeline")

    _msg_count_before_ctx = len(messages)
    messages, _retrieval_text, recalled_backend, _injected_ids = inject_all_context(
        messages, query=query, scenario=scenario, req_type=req_type,
        ide_source=ide_source, system_prompt=system_prompt,
        client_ip=client_ip, user_agent=user_agent,
    )

    if scenario == "coding" and call_fn:
        orch = try_code_orchestration(
            messages, query, call_fn, max_tokens,
            ide_source=ide_source, system_prompt=system_prompt,
            tools=tools, headers=headers, needs_tools=needs_tools,
            scenario=scenario, t0=t0,
            retrieval_text=_retrieval_text, injected_ids=_injected_ids,
        )
        if orch is not None:
            return orch

    # OpenCode x-session-affinity: use session ID 替代 message hash 做 sticky key
    affinity = (headers or {}).get("x-session-affinity", "") if headers else ""
    if affinity:
        sticky_key = f"affinity:{affinity}"
    else:
        sticky_key = sticky_session.compute_key(
            model or "default",
            json.dumps(messages, ensure_ascii=False))

    hmap = health_tracker.get_health_map()
    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario,
                      needs_tools=needs_tools, needs_agent=needs_agent,
                      recalled_backend=recalled_backend,
                      ide_source=ide_source)

    # ── Client model override: resolve model param to specific backend ──
    forced_backend = resolve_backend(model)
    if forced_backend and forced_backend not in backends:
        if health_tracker.is_cooled_down(forced_backend):
            logging.info(
                "model_resolver: forced backend %s is cooled down, "
                "falling back to auto-route %s",
                forced_backend, backends[:3],
            )
        else:
            logging.info(
                "model_resolver: client override %r → %s (inserted at position 0)",
                model, forced_backend,
            )
            backends = [forced_backend] + [b for b in backends if b != forced_backend]

    # ── Backend-aware skill re-injection (now that actual backend is known) ──
    if backends:
        messages = apply_backend_aware_skills(
            messages, backends[0],
            ide_source=ide_source, system_prompt=system_prompt,
        )
    messages_injected = messages

    # ── Inject token budget info for OpenCode-compatible context management ──
    if backends:
        try:
            from opencode_token_bridge import inject_token_budget_info
            messages_injected = inject_token_budget_info(
                messages_injected, backends[0], system_prompt=system_prompt,
            )
        except (ImportError, Exception) as _e:
            logging.debug("routing_engine: token_bridge failed: %s", _e)

    # Auto-compress long conversations before they exceed backend context limits
    try:
        from context_compressor import compress_messages, should_compress
        if backends and should_compress(messages_injected, backends[0]):
            messages_injected = compress_messages(
                messages_injected, backends[0], system_prompt=system_prompt,
                ide_source=ide_source,
            )
    except ImportError as e:
        logging.debug("routing_engine: context compressor not available: %s", e)

    injected_ids = _get_injected_ids(messages[:_msg_count_before_ctx], messages)

    if call_fn:
        complexity = speculative.classify_complexity(query, messages)

        if needs_tools:
            final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens, tools=tools)
        elif complexity == "simple" and req_type in ("ide", "chat"):
            # IDE/OpenCode clients should never be routed through low-quality
            # tunnel/free backends. Use code-tier affinity or fall back to
            # the full evidence-gated coding pool.
            affinity_backends = speculative.get_affinity_backends("code")
            simple_candidates = [b for b in affinity_backends
                                 if not health_tracker.is_cooled_down(b)
                                 and budget_manager.is_budget_available(b)]
            if len(simple_candidates) >= 2:
                try:
                    final_backend, answer, _ = speculative.speculative_call(
                        simple_candidates, call_fn, messages_injected, max_tokens,
                        max_parallel=5, timeout_sec=5.0,
                        needs_tools=needs_tools, ide_source=ide_source)
                except RuntimeError:
                    final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens, tools=tools)
            else:
                final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens)
        elif complexity == "code":
            code_backends = speculative.get_affinity_backends("code")
            code_available = [b for b in code_backends
                              if not health_tracker.is_cooled_down(b)
                              and budget_manager.is_budget_available(b)]
            merged = code_available + [b for b in backends if b not in code_available]
            final_backend, answer, _ = execute(merged, call_fn, messages_injected, max_tokens)
        else:
            final_backend, answer, _ = execute(backends, call_fn, messages_injected, max_tokens)


        if answer and scenario == "coding":
            try:
                from context_pipeline.response_validator import validate_response
                vr = validate_response(answer, query)
                if not vr.passed and len(backends) > 1:
                    retry_backends = [b for b in backends if b != final_backend][:2]
                    if retry_backends:
                        import logging as _rl
                        _rl.getLogger(__name__).info(
                            "response validation failed (score=%.2f, issues=%s), retrying with %s",
                            vr.score, vr.issues[:3], retry_backends,
                        )
                        retry_backend, retry_answer, _ = execute(
                            retry_backends, call_fn, messages_injected, max_tokens)
                        if retry_answer:
                            vr2 = validate_response(retry_answer, query)
                            if vr2.score > vr.score:
                                final_backend, answer = retry_backend, retry_answer
            except Exception as e:
                logging.warning("routing_engine: response validation failed: %s", e)
    else:
        final_backend, answer = backends[0] if backends else "none", ""

    ms = int((time.time() - t0) * 1000)

    result = RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, scenario=scenario, ms=ms,
        fallback_used=bool(final_backend not in ("exhausted", "none") and backends and final_backend != backends[0]),
        skills_injected=injected_ids,
        retrieval_context=_retrieval_text,
    )
    return finalize_route(
        final_backend=final_backend, answer=answer or "",
        backends=backends, messages=messages,
        messages_injected=messages_injected,
        req_type=req_type, scenario=scenario, ms=ms,
        sticky_key=sticky_key, cache_enabled=cache_enabled,
        model=model, result=result,
    )
