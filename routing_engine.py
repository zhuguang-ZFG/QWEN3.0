"""
LiMa Routing Engine — 统一路由入口
合并 smart_router + v3_integration + router_v3 为单一引擎。

架构: classify → select → inject → execute → respond
依赖注入: call_fn 由调用者提供，不耦合任何后端实现

子模块: routing_engine_types / _context / _execute_strategy / _post
公开 API: route, pick_backend, respond（select/execute 见 routing_selector / routing_executor）
"""

from __future__ import annotations

import time
from typing import Callable

import health_tracker
import identity_guard
import skills_injector as skills_mod
import sticky_session
from context_pipeline.retrieval_injection import inject_retrieval_context
from response_builder import build_anthropic_response, build_response, make_chat_id
from routing_classifier import classify, classify_scenario
from routing_intent import analyze_intent, intent_to_prompt_scenario
from routing_engine_context import (
    auto_compress,
    try_recall_backend,
)
from routing_engine_execute_strategy import execute_with_strategy
from routing_engine_post import get_injected_ids, post_route
from lima_constants import MODEL_ID
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


def inject_skills(
    messages: list[dict],
    *,
    backend: str = "",
    ide_source: str = "",
    system_prompt: str = "",
    intent: str = "",
    route_role: str = "",
    scenario: str = "",
) -> list[dict]:
    """根据后端能力和 IDE 注入 skills"""
    return skills_mod.apply_skills(
        backend=backend,
        messages=messages,
        system_prompt=system_prompt,
        ide_source=ide_source,
        intent=intent,
        route_role=route_role,
        scenario=scenario,
    )


def respond(result: RouteResult, fmt: str = "openai", model: str = MODEL_ID) -> dict:
    chat_id = make_chat_id()
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, result.answer, result.backend, model)
    resp = build_response(chat_id, result.answer, result.backend, result.ms)
    resp["x_lima_meta"]["request_type"] = result.request_type
    resp["x_lima_meta"]["skills_injected"] = result.skills_injected
    return resp


def _enrich_with_intent_and_skills(
    messages: list[dict],
    query: str,
    system_prompt: str,
    ide_source: str,
    backends: list[str],
) -> tuple[list[dict], str]:
    """Analyze intent, inject skills, compress. Returns (messages, prompt_scenario)."""
    intent_result = analyze_intent(query, system_prompt=system_prompt, ide=ide_source)
    intent = str(intent_result.get("intent", "chat"))
    route_role = intent if intent.startswith("device_") else ""
    prompt_scenario = intent_to_prompt_scenario(intent) or ""

    messages_out = inject_skills(
        messages,
        backend=backends[0] if backends else "",
        ide_source=ide_source,
        system_prompt=system_prompt,
        intent=intent,
        route_role=route_role,
        scenario=prompt_scenario,
    )
    messages_out = auto_compress(messages_out, backends, system_prompt)
    return messages_out, prompt_scenario


def pick_backend(
    query: str,
    messages: list[dict],
    *,
    fmt: str = "openai",
    ide_source: str = "",
    model: str = "",
    system_prompt: str = "",
    headers: dict | None = None,
    needs_tools: bool = False,
    preferred_backend: str = "",
) -> PickResult:
    """选路前半段：与 route() 共享 classify/inject/select/skills 管线，不执行 HTTP。"""
    req_type, scenario, recall_attempt, retrieval_text = _classify_and_recall(
        query, messages, fmt, ide_source, system_prompt, headers or {},
    )

    sticky_key, backends = _select_backends(
        req_type, scenario, recall_attempt, messages, needs_tools, preferred_backend, model,
    )

    messages, prompt_scenario = _enrich_with_intent_and_skills(messages, query, system_prompt, ide_source, backends)
    backend = backends[0] if backends else "longcat_chat"
    return PickResult(
        backend=backend,
        backends=backends,
        messages=messages,
        request_type=req_type,
        scenario=prompt_scenario,
        retrieval_context=retrieval_text or "",
        sticky_key=sticky_key,
    )


def _classify_and_recall(
    query: str,
    messages: list[dict],
    fmt: str,
    ide_source: str,
    system_prompt: str,
    headers: dict,
) -> tuple[str, str, str | None, str]:
    """Classify request type/scenario and recall backend + retrieval context."""
    req_type = classify(query, messages, fmt=fmt, ide_source=ide_source, system_prompt=system_prompt, headers=headers)
    scenario = classify_scenario(messages, query=query, ide_source=ide_source, request_type=req_type)
    recall_attempt = try_recall_backend(messages, scenario)
    messages, retrieval_text = inject_retrieval_context(messages)
    return req_type, scenario, recall_attempt, retrieval_text


def _select_backends(
    req_type: str,
    scenario: str,
    recall_attempt: str | None,
    messages: list[dict],
    needs_tools: bool,
    preferred_backend: str,
    model: str,
) -> tuple[str, list[str]]:
    """Select backends based on health, sticky session, and recall."""
    sticky_key = sticky_session.compute_key(model or "default", messages)
    hmap = health_tracker.get_health_map()
    backends = select(
        req_type, hmap, sticky_key=sticky_key, scenario=scenario,
        needs_tools=needs_tools, recalled_backend=recall_attempt,
        preferred_backend=preferred_backend or "",
    )
    return sticky_key, backends


def _identity_shortcut(query: str, channel_role: str, t0: float) -> RouteResult | None:
    """检测身份类问题并返回提前结果；无命中返回 None。"""
    identity_answer = identity_guard.detect_identity_question(query, channel_role=channel_role)
    if identity_answer:
        ms = int((time.time() - t0) * 1000)
        return RouteResult(backend="identity_guard", answer=identity_answer, request_type="identity", ms=ms)
    return None


def _pick_for_route(
    query: str,
    messages: list[dict],
    fmt: str,
    ide_source: str,
    model: str,
    system_prompt: str,
    headers: dict | None,
    needs_tools: bool,
    preferred_backend: str,
) -> PickResult:
    """包装 pick_backend，避免 route() 被大量关键字参数撑开。"""
    return pick_backend(
        query,
        messages,
        fmt=fmt,
        ide_source=ide_source,
        model=model,
        system_prompt=system_prompt,
        headers=headers,
        needs_tools=needs_tools,
        preferred_backend=preferred_backend or "",
    )


def _build_route_result(
    t0: float,
    picked: PickResult,
    final_backend: str,
    answer: str,
    messages: list[dict],
    injected_ids: list,
    backends: list[str],
    original_backend: str,
    fallback_used: bool,
) -> RouteResult:
    """构造最终 RouteResult 并计算耗时；先执行 post_route 上报。"""
    ms = int((time.time() - t0) * 1000)
    post_route(answer, final_backend, backends, picked.messages, messages, picked.request_type, picked.scenario, ms)
    return RouteResult(
        backend=final_backend,
        answer=answer,
        request_type=picked.request_type,
        scenario=picked.scenario,
        ms=ms,
        fallback_used=fallback_used,
        skills_injected=injected_ids,
        retrieval_context=picked.retrieval_context,
    )


def route(
    query: str,
    messages: list[dict],
    *,
    fmt: str = "openai",
    ide_source: str = "",
    model: str = "",
    max_tokens: int = 4096,
    system_prompt: str = "",
    headers: dict | None = None,
    call_fn: Callable | None = None,
    cache_enabled: bool = True,
    channel_role: str = "default",
    needs_tools: bool = False,
    tools: list[dict] | None = None,
    preferred_backend: str = "",
) -> RouteResult:
    """统一路由入口。call_fn(backend, messages, max_tokens) -> str"""
    t0 = time.time()
    shortcut = _identity_shortcut(query, channel_role, t0)
    if shortcut:
        return shortcut
    picked = _pick_for_route(
        query, messages, fmt, ide_source, model, system_prompt, headers, needs_tools, preferred_backend
    )
    backends = picked.backends
    injected_ids = get_injected_ids(messages, picked.messages)
    if call_fn:
        final_backend, answer = execute_with_strategy(
            call_fn,
            backends,
            picked.messages,
            max_tokens,
            query,
            picked.request_type,
            picked.scenario,
            needs_tools,
            tools,
            picked.sticky_key,
        )
    else:
        final_backend, answer = backends[0] if backends else "none", ""
    original_backend = backends[0] if backends else "none"
    fallback_used = bool(final_backend not in ("exhausted", "none") and backends and final_backend != original_backend)
    args = (t0, picked, final_backend, answer, messages, injected_ids, backends, original_backend, fallback_used)
    return _build_route_result(*args)
