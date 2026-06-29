"""Small route() helpers to keep routing_engine.py under size limits."""

from __future__ import annotations

import time

import identity_guard
from routing_engine_post import post_route
from routing_engine_trace import trace_span
from routing_engine_types import PickResult, RouteResult


def identity_shortcut(query: str, channel_role: str, t0: float) -> RouteResult | None:
    """检测身份类问题并返回提前结果；无命中返回 None。"""
    with trace_span("identity", channel_role=channel_role):
        identity_answer = identity_guard.detect_identity_question(query, channel_role=channel_role)
        if identity_answer:
            ms = int((time.time() - t0) * 1000)
            return RouteResult(backend="identity_guard", answer=identity_answer, request_type="identity", ms=ms)
    return None


def build_route_result(
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
    with trace_span(
        "post_process",
        final_backend=final_backend,
        fallback_used=fallback_used,
        request_type=picked.request_type,
        scenario=picked.scenario,
    ) as span:
        post_route(answer, final_backend, backends, picked.messages, messages, picked.request_type, picked.scenario, ms)
        if span is not None:
            span.metadata["ms"] = ms
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


def apply_non_stream_last_resort(final_backend: str, answer: str, messages: list) -> tuple[str, str]:
    """AUDIT-4-F5：非流式路径对齐流式降级——全部后端耗尽时调用 Cloudflare 终极降级，
    避免非流式客户端（如 IDE）在全局故障时收到空内容。"""
    if final_backend != "exhausted" or answer:
        return final_backend, answer
    try:
        from server_bootstrap import last_resort_call

        fallback_answer = last_resort_call(messages)
        if fallback_answer:
            return "cloudflare-last-resort", fallback_answer
    except Exception as exc:
        import logging

        logging.getLogger("routing_engine").warning(
            "non-stream last_resort_call failed: %s", exc, exc_info=True
        )
    return final_backend, answer
