"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现

子模块: routing_engine_types / _context / _execute_strategy / _post
公开 API: route, pick_backend, respond（select/execute 见 routing_selector / routing_executor）
"""

from __future__ import annotations

import json
import time
from typing import Callable

import health_tracker
import identity_guard
import skills_injector as skills_mod
import sticky_session
from context_pipeline.retrieval_injection import inject_retrieval_context
from response_builder import build_anthropic_response, build_response, make_chat_id
from routing_classifier import classify, classify_scenario
from routing_engine_context import (
    assess_complexity,
    auto_compress,
    inject_coding_context,
    try_recall_backend,
)
from routing_engine_execute_strategy import execute_with_strategy
from routing_engine_post import get_injected_ids, post_route
from routing_engine_types import PickResult, RouteResult
from routing_selector import select

__all__ = [
    "RouteResult",
    "PickResult",
    "classify",
    "classify_scenario",
    "inject_skills",
    "respond",
    "pick_backend",
    "route",
]


def inject_skills(messages: list[dict], *,
                  backend: str = "", ide_source: str = "",
                  system_prompt: str = "") -> list[dict]:
    """根据后端能力和 IDE 注入 skills"""
    return skills_mod.apply_skills(
        backend=backend, messages=messages,
        system_prompt=system_prompt, ide_source=ide_source,
    )


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
                 needs_tools: bool = False,
                 preferred_backend: str = "") -> PickResult:
    """选路前半段：与 route() 共享 classify/inject/select/skills 管线，不执行 HTTP。"""
    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source,
                        system_prompt=system_prompt, headers=headers or {})
    scenario = classify_scenario(query, messages,
                                 ide_source=ide_source, request_type=req_type)

    recalled_backend = try_recall_backend(messages, scenario)
    messages, retrieval_text = inject_retrieval_context(messages)
    messages, _code_context_text = inject_coding_context(messages, scenario, query)
    complexity_info = assess_complexity(messages, ide_source)

    sticky_key = sticky_session.compute_key(
        model or "default", json.dumps(messages, ensure_ascii=False))

    hmap = health_tracker.get_health_map()
    backends = select(req_type, hmap, sticky_key=sticky_key, scenario=scenario,
                      needs_tools=needs_tools, recalled_backend=recalled_backend,
                      preferred_backend=preferred_backend or "",
                      complexity=complexity_info)

    messages_injected = inject_skills(
        messages, backend=backends[0] if backends else "",
        ide_source=ide_source, system_prompt=system_prompt)
    messages_injected = auto_compress(messages_injected, backends, system_prompt)

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
          tools: list[dict] | None = None,
          preferred_backend: str = "") -> RouteResult:
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
        preferred_backend=preferred_backend or "",
    )
    req_type = picked.request_type
    scenario = picked.scenario
    backends = picked.backends
    messages_injected = picked.messages
    sticky_key = picked.sticky_key
    injected_ids = get_injected_ids(messages, messages_injected)

    if call_fn:
        final_backend, answer = execute_with_strategy(
            call_fn, backends, messages_injected, max_tokens,
            query, req_type, scenario, needs_tools, tools, sticky_key)
    else:
        final_backend, answer = backends[0] if backends else "none", ""

    ms = int((time.time() - t0) * 1000)
    post_route(answer, final_backend, backends, messages_injected,
               messages, req_type, scenario, ms)

    return RouteResult(
        backend=final_backend, answer=answer,
        request_type=req_type, scenario=scenario, ms=ms,
        fallback_used=bool(
            final_backend not in ("exhausted", "none") and backends
            and final_backend != backends[0],
        ),
        skills_injected=injected_ids,
        retrieval_context=picked.retrieval_context,
    )
