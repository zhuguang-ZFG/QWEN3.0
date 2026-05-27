"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现
"""

import json
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
    resp = build_response(chat_id, result.answer, result.backend, result.ms)
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
          tools: list[dict] | None = None) -> RouteResult:
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
            return RouteResult(backend="cache", answer=answer,
                               request_type="cache_hit", ms=ms)

    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source,
                        system_prompt=system_prompt, headers=headers or {})

    scenario = classify_scenario(query, messages,
                                 ide_source=ide_source, request_type=req_type)

    try:
        from context_pipeline.skill_store import get_skill_store
        get_skill_store().recall(messages, scenario)
    except ImportError:
        pass

    messages, _retrieval_text = inject_retrieval_context(messages)

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
        except Exception as e:
            import logging as _logging
            _logging.debug("code_context_injection failed: %s", e)

    try:
        from context_pipeline.complexity import assess_complexity
        raw_msgs = [{"role": m.get("role", ""), "content": m.get("content", "")} if isinstance(m, dict) else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")} for m in messages]
        _complexity_score = assess_complexity(raw_msgs, ide=ide_source)
    except ImportError:
        pass

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
    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario,
                      needs_tools=needs_tools)

    messages_injected = inject_skills(
        messages, backend=backends[0] if backends else "",
        ide_source=ide_source, system_prompt=system_prompt)

    injected_ids = _get_injected_ids(messages, messages_injected)

    if call_fn:
        complexity = speculative.classify_complexity(query, messages)

        if complexity == "simple" and req_type in ("ide", "chat"):
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
            except Exception:
                pass
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

    return RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, scenario=scenario, ms=ms,
        fallback_used=bool(final_backend not in ("exhausted", "none") and backends and final_backend != backends[0]),
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
