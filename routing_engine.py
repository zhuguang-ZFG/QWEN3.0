"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

import health_tracker
import budget_manager
import identity_guard
import router_v3
import semantic_cache
import skills_injector as skills_mod
import speculative
import sticky_session
from context_pipeline.retrieval_injection import inject_retrieval_context
from response_builder import build_anthropic_response, build_response, make_chat_id
from response_cleaner import clean_response
from route_post_process import apply_post_route_integrations
from routing_classifier import classify, classify_scenario
from routing_executor import execute
from model_resolver import resolve_backend
from routing_selector import select

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
    usage: dict | None = None
    injection_meta: dict = field(default_factory=dict)


def inject_skills(messages: list[dict], *,
                  backend: str = "", ide_source: str = "",
                  system_prompt: str = "") -> list[dict]:
    """根据后端能力和 IDE 注入 skills"""
    return skills_mod.apply_skills(
        backend=backend, messages=messages,
        system_prompt=system_prompt, ide_source=ide_source)


def respond(result: RouteResult, fmt: str = "openai",
            model: str = "lima-1.3") -> dict:
    chat_id = make_chat_id()
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, result.answer, result.backend, model)
    resp = build_response(chat_id, result.answer, result.backend, result.ms,
                          usage=result.usage)
    resp["x_lima_meta"]["request_type"] = result.request_type
    resp["x_lima_meta"]["skills_injected"] = result.skills_injected
    return resp


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

    try:
        from context_injection_trace import begin_trace

        begin_trace(scenario=scenario, request_type=req_type)
    except ImportError:
        pass

    _recalled_backend = ""
    try:
        from context_pipeline.skill_store import get_skill_store
        recalled = get_skill_store().recall(messages, scenario)
        if recalled:
            _recalled_backend = recalled.backend
    except ImportError as e:
        logging.debug("routing_engine: skill_store not available: %s", e)

    messages, _retrieval_text = inject_retrieval_context(messages)
    try:
        from context_injection_trace import record_retrieval

        record_retrieval(_retrieval_text)
    except ImportError:
        pass

    # ── Enriched context: date/time + location + device ──
    try:
        from context_pipeline.enrich_context import inject_enriched_context
        messages = inject_enriched_context(
            messages, client_ip=client_ip, user_agent=user_agent,
        )
    except Exception as e:
        logging.debug("routing_engine: enrich_context injection failed: %s", e)

    # ── Web search context: detect + search + inject ──
    _web_search_text = ""
    try:
        from context_pipeline.web_search_context import inject_web_search_context
        messages, _web_search_text = inject_web_search_context(query, messages)
        if _web_search_text:
            _retrieval_text = (_retrieval_text + "\n" + _web_search_text).strip()
            try:
                from context_injection_trace import record_web_search

                record_web_search(_web_search_text)
            except ImportError:
                pass
    except Exception as e:
        logging.debug("routing_engine: web_search_context injection failed: %s", e)

    _code_context_text = ""
    if scenario == "coding":
        try:
            from context_pipeline.code_context_injection import scan_and_build_context
            _code_context_text = scan_and_build_context(query, messages)
            if _code_context_text:
                code_ctx_msg = {"role": "system", "content": _code_context_text}
                if messages and messages[0].get("role") == "system":
                    messages.insert(1, code_ctx_msg)
                else:
                    messages.insert(0, code_ctx_msg)
                try:
                    from context_injection_trace import record_code_context

                    record_code_context(_code_context_text)
                except ImportError:
                    pass
        except Exception as e:
            import logging as _logging
            _logging.debug("code_context_injection failed: %s", e)

        # Typed memory recall is now unified in session_memory.processor (Tier 6)
        # — no longer queried independently here.

    try:
        from context_pipeline.complexity import assess_complexity
        raw_msgs = [{"role": m.get("role", ""), "content": m.get("content", "")} if isinstance(m, dict) else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")} for m in messages]
        _complexity_score = assess_complexity(raw_msgs, ide=ide_source)
    except ImportError as e:
        logging.debug("routing_engine: complexity assessment not available: %s", e)

    # ── Skills injection (must happen BEFORE code_orchestrator to ensure
    #     IDE-customized prompts are available to all execution paths) ──
    _msg_count_before = len(messages)
    try:
        messages = inject_skills(
            messages, backend="",
            ide_source=ide_source, system_prompt=system_prompt)
    except Exception as _e:
        logging.warning(f"[SKILLS] early injection failed: {type(_e).__name__}: {_e}")
    _injected_ids = _get_injected_ids(list(messages[:_msg_count_before]), messages)
    try:
        from context_injection_trace import record_skills

        record_skills(_injected_ids)
    except ImportError:
        pass

    if scenario == "coding" and call_fn:
        try:
            # ── Inject OpenCode tool-aware prompts before code orchestration ──
            try:
                from opencode_tool_aware import inject_opencode_prompt
                messages = inject_opencode_prompt(
                    messages, backend="", system_prompt=system_prompt,
                    tools=tools, headers=headers or {},
                )
            except (ImportError, Exception) as _e:
                logging.debug("routing_engine: opencode_tool_aware failed: %s", _e)

            # ── Inject reasoning bridge (thinking reminder + provider prompt) ──
            try:
                from opencode_reasoning_bridge import (
                    inject_thinking_reminder, select_provider_system_prompt,
                )
                # Get estimated backend for this coding path
                _est_backend = ""
                try:
                    from routing_selector import select as _rselect
                    _hmap = health_tracker.get_health_map()
                    _candidates = _rselect("ide", _hmap, scenario="coding",
                                            needs_tools=needs_tools, ide_source=ide_source)
                    _est_backend = _candidates[0] if _candidates else ""
                except Exception:
                    pass
                if _est_backend:
                    messages = inject_thinking_reminder(messages, _est_backend)
                    _provider_hint = select_provider_system_prompt(_est_backend)
                    if _provider_hint:
                        _sp_msg = {"role": "system", "content": _provider_hint}
                        _sys_idx = next((i for i, m in enumerate(messages)
                                        if m.get("role") == "system"), -1)
                        if _sys_idx >= 0:
                            _old = messages[_sys_idx].get("content", "")
                            if isinstance(_old, str):
                                messages[_sys_idx] = {**messages[_sys_idx],
                                    "content": _old.rstrip() + "\n" + _provider_hint}
                # Inject sequential tool hint for weak backends
                if _est_backend:
                    try:
                        from opencode_tool_splitter import (
                            should_inject_sequential_hint, build_sequential_tool_prompt,
                        )
                        if should_inject_sequential_hint(_est_backend):
                            _seq_hint = build_sequential_tool_prompt(tools)
                            if _seq_hint:
                                _sys_idx = next((i for i, m in enumerate(messages)
                                                if m.get("role") == "system"), -1)
                                if _sys_idx >= 0:
                                    _old = messages[_sys_idx].get("content", "")
                                    if isinstance(_old, str):
                                        messages[_sys_idx] = {**messages[_sys_idx],
                                            "content": _old.rstrip() + "\n" + _seq_hint}
                                else:
                                    messages.insert(0, {"role": "system", "content": _seq_hint})
                    except (ImportError, Exception) as _e2:
                        logging.debug("routing_engine: tool_splitter hint failed: %s", _e2)
            except (ImportError, Exception) as _e:
                logging.debug("routing_engine: reasoning_bridge failed: %s", _e)

            import code_orchestrator
            orch_result = code_orchestrator.handle(
                query, messages, call_fn, max_tokens,
                ide_source=ide_source,
            )
            if orch_result.get("answer"):
                ms = int((time.time() - t0) * 1000)
                return _with_injection_meta(RouteResult(
                    backend=orch_result["backend"],
                    answer=orch_result["answer"],
                    request_type=f"code_{orch_result['tier']}",
                    ms=ms, scenario=scenario,
                    retrieval_context=_retrieval_text,
                    skills_injected=_injected_ids), orch_result["backend"])
        except Exception as e:
            import logging as _logging
            _logging.warning(f"[ORCH] code_orchestrator failed: {type(e).__name__}: {e}")

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
                      needs_tools=needs_tools, recalled_backend=_recalled_backend,
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

    # Skills already injected above; reuse injected messages directly
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
        from context_compressor import should_compress, compress_messages
        if backends and should_compress(messages_injected, backends[0]):
            messages_injected = compress_messages(
                messages_injected, backends[0], system_prompt=system_prompt,
                ide_source=ide_source,
            )
    except ImportError as e:
        logging.debug("routing_engine: context compressor not available: %s", e)

    injected_ids = _injected_ids  # computed during early skills injection above

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

        if final_backend != "exhausted":
            sticky_session.pin_backend(sticky_key, final_backend)
            if cache_enabled and answer:
                to_cache = clean_response(answer, final_backend) or answer
                semantic_cache.put(model or "default", messages, 0, to_cache)

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

    apply_post_route_integrations(
        final_backend=final_backend,
        answer=answer or "",
        backends=backends,
        messages_injected=messages_injected,
        messages=messages,
        req_type=req_type,
        scenario=scenario,
        ms=ms,
    )

    return _with_injection_meta(RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, scenario=scenario, ms=ms,
        fallback_used=bool(final_backend not in ("exhausted", "none") and backends and final_backend != backends[0]),
        skills_injected=injected_ids,
        retrieval_context=_retrieval_text,
    ), final_backend)


def _with_injection_meta(result: RouteResult, backend: str = "") -> RouteResult:
    try:
        from context_injection_trace import finish_trace

        trace = finish_trace(backend=backend)
        if trace:
            result.injection_meta = trace.to_meta()
    except ImportError:
        pass
    return result


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
