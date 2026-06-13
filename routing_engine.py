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

_log = logging.getLogger(__name__)

import health_tracker
import budget_manager
import identity_guard
import router_v3
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
    "PickResult",
    "classify",
    "classify_scenario",
    "select",
    "inject_skills",
    "execute",
    "respond",
    "pick_backend",
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


@dataclass
class PickResult:
    """选路结果（classify → inject → select → skills/compress，不执行 HTTP）。"""

    backend: str
    backends: list[str]
    messages: list[dict]
    request_type: str = "chat"
    scenario: str = ""
    retrieval_context: str = ""
    sticky_key: str = ""


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


def pick_backend(query: str, messages: list[dict], *,
                 fmt: str = "openai", ide_source: str = "",
                 model: str = "", system_prompt: str = "",
                 headers: dict | None = None,
                 needs_tools: bool = False) -> PickResult:
    """选路前半段：与 route() 共享 classify/inject/select/skills 管线，不执行 HTTP。"""
    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source,
                        system_prompt=system_prompt, headers=headers or {})
    scenario = classify_scenario(query, messages,
                                 ide_source=ide_source, request_type=req_type)

    recalled_backend = _try_recall_backend(messages, scenario)
    messages, retrieval_text = inject_retrieval_context(messages)
    messages, _code_context_text = _inject_coding_context(messages, scenario, query)
    complexity_info = _assess_complexity(messages, ide_source)

    sticky_key = sticky_session.compute_key(
        model or "default", json.dumps(messages, ensure_ascii=False))

    hmap = health_tracker.get_health_map()
    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario,
                      needs_tools=needs_tools, recalled_backend=recalled_backend,
                      complexity=complexity_info)

    messages_injected = inject_skills(
        messages, backend=backends[0] if backends else "",
        ide_source=ide_source, system_prompt=system_prompt)
    messages_injected = _auto_compress(messages_injected, backends, system_prompt)

    backend = backends[0] if backends else "longcat_chat"
    return PickResult(
        backend=backend,
        backends=backends,
        messages=messages_injected,
        request_type=req_type,
        scenario=scenario,
        retrieval_context=retrieval_text or "",
        sticky_key=sticky_key,
    )


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

    picked = pick_backend(
        query, messages, fmt=fmt, ide_source=ide_source, model=model,
        system_prompt=system_prompt, headers=headers, needs_tools=needs_tools,
    )
    req_type = picked.request_type
    scenario = picked.scenario
    backends = picked.backends
    messages_injected = picked.messages
    sticky_key = picked.sticky_key
    injected_ids = _get_injected_ids(messages, messages_injected)

    if call_fn:
        final_backend, answer = _execute_with_strategy(
            call_fn, backends, messages_injected, max_tokens,
            query, req_type, scenario, needs_tools, tools, sticky_key)
    else:
        final_backend, answer = backends[0] if backends else "none", ""

    ms = int((time.time() - t0) * 1000)
    _post_route(answer, final_backend, backends, messages_injected,
                messages, req_type, scenario, ms)

    return RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, scenario=scenario, ms=ms,
        fallback_used=bool(final_backend not in ("exhausted", "none") and backends and final_backend != backends[0]),
        skills_injected=injected_ids,
        retrieval_context=picked.retrieval_context,
    )


def _try_recall_backend(messages: list[dict], scenario: str) -> str:
    """从 skill store 尝试召回推荐后端。"""
    try:
        from context_pipeline.skill_store import get_skill_store
        recalled = get_skill_store().recall(messages, scenario)
        if recalled:
            return recalled.backend
    except ImportError:
        pass
    return ""


def _inject_coding_context(messages: list[dict], scenario: str,
                           query: str) -> tuple[list[dict], str]:
    """为 coding 场景注入代码上下文和历史记忆。返回 (messages, code_context_text)。"""
    code_context_text = ""
    if scenario != "coding":
        return messages, code_context_text

    try:
        from context_pipeline.code_context_injection import scan_and_build_context
        code_context_text = scan_and_build_context(query, messages)
        if code_context_text:
            code_ctx_msg = {"role": "system", "content": code_context_text}
            if messages and messages[0].get("role") == "system":
                messages.insert(1, code_ctx_msg)
            else:
                messages.insert(0, code_ctx_msg)
    except Exception as e:
        _log.debug("code_context_injection failed: %s", e)

    try:
        from session_memory.store_promote import query_by_type
        memory_parts: list[str] = []
        for mt in ("code_fact", "routing_lesson"):
            for mem in query_by_type(mt, limit=3):
                memory_parts.append(f"[{mt}] {mem.summary}")
        if memory_parts:
            memory_ctx = "Past coding decisions:\n" + "\n".join(memory_parts)
            mem_msg = {"role": "system", "content": memory_ctx}
            insert_pos = 2 if messages and messages[0].get("role") == "system" else 1
            messages.insert(insert_pos, mem_msg)
    except Exception as exc:
        _log.debug("routing_engine.py: {}", type(exc).__name__)

    return messages, code_context_text


def _assess_complexity(messages: list[dict], ide_source: str):
    """评估请求复杂度，返回 complexity info 或 None。"""
    try:
        from context_pipeline.complexity import assess_complexity
        raw_msgs = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            if isinstance(m, dict)
            else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
            for m in messages
        ]
        return assess_complexity(raw_msgs, ide=ide_source)
    except (ImportError, Exception):
        return None


def _auto_compress(messages: list[dict], backends: list[str],
                   system_prompt: str) -> list[dict]:
    """自动压缩过长对话，防止超出后端上下文限制。"""
    try:
        from context_compressor import should_compress, compress_messages
        if backends and should_compress(messages, backends[0]):
            return compress_messages(messages, backends[0], system_prompt=system_prompt)
    except ImportError:
        pass
    return messages


def _execute_with_strategy(
    call_fn: Callable, backends: list[str], messages: list[dict],
    max_tokens: int, query: str, req_type: str, scenario: str,
    needs_tools: bool, tools: list[dict] | None, sticky_key: str,
) -> tuple[str, str]:
    """根据复杂度选择执行策略（投机/代码优先/标准），返回 (backend, answer)。"""
    complexity = speculative.classify_complexity(query, messages)

    if needs_tools:
        final_backend, answer, _ = execute(
            backends, call_fn, messages, max_tokens,
            tools=tools, scenario=scenario, request_type=req_type,
        )
    elif complexity == "simple" and req_type in ("ide", "chat"):
        final_backend, answer = _try_speculative(
            backends, call_fn, messages, max_tokens, scenario, req_type)
    elif complexity == "code":
        final_backend, answer = _execute_code_priority(
            backends, call_fn, messages, max_tokens, scenario, req_type)
    else:
        final_backend, answer, _ = execute(
            backends, call_fn, messages, max_tokens,
            scenario=scenario, request_type=req_type,
        )

    if final_backend != "exhausted":
        sticky_session.pin_backend(sticky_key, final_backend)

    if answer and scenario == "coding":
        final_backend, answer = _maybe_quality_retry(
            final_backend, answer, backends, call_fn, messages, max_tokens,
            query, scenario, req_type)

    return final_backend, answer


def _try_speculative(
    backends: list[str], call_fn: Callable, messages: list[dict],
    max_tokens: int, scenario: str, req_type: str,
) -> tuple[str, str]:
    """尝试投机执行，回退到标准执行。"""
    affinity_backends = speculative.get_affinity_backends("simple")
    spec_candidates = [b for b in affinity_backends
                       if not health_tracker.is_cooled_down(b)
                       and budget_manager.is_budget_available(b)
                       and speculative.is_historically_fast(b)]
    if len(spec_candidates) >= 2:
        try:
            return speculative.speculative_call(
                spec_candidates, call_fn, messages, max_tokens,
                max_parallel=5, timeout_sec=5.0,
                scenario=scenario, request_type=req_type,
            )[:2]
        except RuntimeError:
            pass
    final_backend, answer, _ = execute(
        backends, call_fn, messages, max_tokens,
        scenario=scenario, request_type=req_type,
    )
    return final_backend, answer


def _execute_code_priority(
    backends: list[str], call_fn: Callable, messages: list[dict],
    max_tokens: int, scenario: str, req_type: str,
) -> tuple[str, str]:
    """代码场景优先使用 code affinity 后端。"""
    code_backends = speculative.get_affinity_backends("code")
    code_available = [b for b in code_backends
                      if not health_tracker.is_cooled_down(b)
                      and budget_manager.is_budget_available(b)]
    merged = code_available + [b for b in backends if b not in code_available]
    final_backend, answer, _ = execute(
        merged, call_fn, messages, max_tokens,
        scenario=scenario, request_type=req_type,
    )
    return final_backend, answer


def _maybe_quality_retry(
    final_backend: str, answer: str, backends: list[str],
    call_fn: Callable, messages: list[dict], max_tokens: int,
    query: str, scenario: str, req_type: str,
) -> tuple[str, str]:
    """coding 场景质量验证不通过时自动重试。"""
    try:
        from context_pipeline.response_validator import validate_response
        vr = validate_response(answer, query)
        if not vr.passed and len(backends) > 1:
            retry_backends = [b for b in backends if b != final_backend][:2]
            if retry_backends:
                _log.info(
                    "response validation failed (score=%.2f, issues=%s), retrying with %s",
                    vr.score, vr.issues[:3], retry_backends,
                )
                retry_backend, retry_answer, _ = execute(
                    retry_backends, call_fn, messages, max_tokens,
                    scenario=scenario, request_type=req_type,
                )
                if retry_answer:
                    vr2 = validate_response(retry_answer, query)
                    if vr2.score > vr.score:
                        try:
                            health_tracker.record_failure(final_backend, 200, "quality_retry")
                        except Exception as exc:
                            _log.debug("routing_engine.py: {}", type(exc).__name__)
                        return retry_backend, retry_answer
    except Exception as exc:
        _log.debug("routing_engine.py: {}", type(exc).__name__)
    return final_backend, answer


def _post_route(answer: str | None, final_backend: str, backends: list[str],
                messages_injected: list[dict], messages: list[dict],
                req_type: str, scenario: str, ms: int):
    """路由后处理：post-route 集成、事件记录、反馈闭环。"""
    apply_post_route_integrations(
        final_backend=final_backend, answer=answer or "",
        backends=backends, messages_injected=messages_injected,
        messages=messages, req_type=req_type, scenario=scenario, ms=ms,
    )

    fallback_used = bool(
        final_backend not in ("exhausted", "none") and backends
        and final_backend != backends[0])
    success = bool(answer and len(answer) > 5)

    try:
        from routes.agent_events import record_event
        record_event("routing_decision", {
            "backend": final_backend, "scenario": scenario, "req_type": req_type,
            "latency_ms": ms, "success": success, "fallback_used": fallback_used,
        })
    except Exception as exc:
        _log.debug("routing_engine.py: {}", type(exc).__name__)

    try:
        from routing_loop.feedback_bridge import on_request_complete
        on_request_complete(
            request_id=make_chat_id(), scenario=scenario, messages=messages,
            backend=final_backend, success=success, latency_ms=float(ms),
            fallback_used=fallback_used,
        )
    except Exception as _fb_exc:
        _log.warning("feedback_bridge error: %s", _fb_exc)


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
