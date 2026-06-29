"""LiMa Routing Engine — 统一路由入口（classify → select → inject → execute → respond）。"""

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
from routing_engine_cache import store_cached_response, traced_lookup_cached_response
from routing_engine_helpers import apply_non_stream_last_resort, build_route_result, identity_shortcut
from routing_engine_intent import resolve_intent
from routing_intent import intent_to_prompt_scenario
from routing_engine_context import (
    auto_compress,
    try_recall_backend,
)
from routing_engine_execute_strategy import execute_with_strategy
from routing_engine_post import get_injected_ids, post_route
from routing_engine_trace import trace_span
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
    precomputed_intent: dict | None = None,
) -> tuple[list[dict], str]:
    """Analyze intent (with optional semantic-router shortcut), inject skills, compress."""
    with trace_span("skills") as span:
        intent = resolve_intent(query, system_prompt, ide_source, precomputed_intent)
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
        if span is not None:
            span.metadata["intent"] = intent
            span.metadata["scenario"] = prompt_scenario
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
    precomputed_intent: dict | None = None,
) -> PickResult:
    """选路前半段：与 route() 共享 classify/inject/select/skills 管线，不执行 HTTP。"""
    req_type, scenario, recall_attempt, retrieval_text = _classify_and_recall(
        query,
        messages,
        fmt,
        ide_source,
        system_prompt,
        headers or {},
    )

    sticky_key, backends = _select_backends(
        req_type,
        scenario,
        recall_attempt,
        messages,
        needs_tools,
        preferred_backend,
        model,
    )

    messages, prompt_scenario = _enrich_with_intent_and_skills(
        messages, query, system_prompt, ide_source, backends, precomputed_intent
    )
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
    with trace_span("classify") as span:
        req_type = classify(
            query, messages, fmt=fmt, ide_source=ide_source, system_prompt=system_prompt, headers=headers
        )
        if span is not None:
            span.metadata["request_type"] = req_type

    # AUDIT-8-P9: v3.0 起编码能力退役，classify_scenario 永远返回 chat；
    # retrieval 也是 no-op。直接硬编码，避免热路径上的 dataclass 校验与函数调用开销。
    scenario = "chat"
    with trace_span("scenario") as span:
        if span is not None:
            span.metadata["scenario"] = scenario

    with trace_span("recall") as span:
        recall_attempt = try_recall_backend(messages, scenario)
        if span is not None:
            span.metadata["recalled_backend"] = recall_attempt

    retrieval_text = ""
    with trace_span("retrieval") as span:
        if span is not None:
            span.metadata["has_context"] = False

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
    with trace_span("select") as span:
        sticky_key = sticky_session.compute_key(model or "default", messages)
        hmap = health_tracker.get_health_map()
        backends = select(
            req_type,
            hmap,
            sticky_key=sticky_key,
            scenario=scenario,
            needs_tools=needs_tools,
            recalled_backend=recall_attempt,
            preferred_backend=preferred_backend or "",
        )
        if span is not None:
            span.metadata["backends"] = backends
        return sticky_key, backends


def _execute_route_call(
    call_fn: Callable | None,
    picked: PickResult,
    max_tokens: int,
    query: str,
    needs_tools: bool,
    tools: list[dict] | None,
) -> tuple[str, str]:
    """Execute backend call or return empty placeholder when no call_fn."""
    if not call_fn:
        return picked.backends[0] if picked.backends else "none", ""
    return execute_with_strategy(
        call_fn,
        picked.backends,
        picked.messages,
        max_tokens,
        query,
        picked.request_type,
        picked.scenario,
        needs_tools,
        tools,
        picked.sticky_key,
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
    precomputed_intent: dict | None = None,
) -> RouteResult:
    """统一路由入口。call_fn(backend, messages, max_tokens) -> str"""
    t0 = time.time()
    shortcut = identity_shortcut(query, channel_role, t0)
    if shortcut:
        return shortcut
    picked = pick_backend(
        query,
        messages,
        fmt=fmt,
        ide_source=ide_source,
        model=model,
        system_prompt=system_prompt,
        headers=headers,
        needs_tools=needs_tools,
        preferred_backend=preferred_backend or "",
        precomputed_intent=precomputed_intent,
    )
    backends = picked.backends
    original_backend = backends[0] if backends else "none"
    injected_ids = get_injected_ids(messages, picked.messages)

    cached = _check_cache_or_none(query, picked, cache_enabled)
    if cached is not None:
        return build_route_result(t0, picked, original_backend, cached, messages, injected_ids, backends, original_backend, False)  # fmt: skip

    final_backend, answer = _execute_route_call(call_fn, picked, max_tokens, query, needs_tools, tools)
    store_cached_response(query, answer, picked.request_type)
    final_backend, answer = apply_non_stream_last_resort(final_backend, answer, picked.messages)
    fallback_used = bool(final_backend not in ("exhausted", "none") and backends and final_backend != original_backend)
    return build_route_result(
        t0, picked, final_backend, answer, messages, injected_ids, backends, original_backend, fallback_used
    )


def _check_cache_or_none(query, picked, cache_enabled):
    """AUDIT-8-P2：缓存查询提取，控制 route() 函数体积。命中返回 answer，否则 None。"""
    cached_answer, _, _ = traced_lookup_cached_response(query, picked.request_type, cache_enabled)
    return cached_answer
