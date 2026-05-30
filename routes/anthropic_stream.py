"""routes/anthropic_stream.py — Anthropic Messages API streaming facade (CQ-099)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import smart_router
from response_builder import extract_query, messages_to_dicts
from routes.anthropic_stream_branches import (
    StreamContext,
    apply_quality_fallback,
    resolve_normal_route,
    resolve_thinking,
    stream_image_intent,
    stream_speculative_path,
)
from routes.anthropic_stream_sse import stream_text_as_sse

_log = logging.getLogger(__name__)


@dataclass
class AnthropicStreamDeps:
    last_resort_call: Callable[..., str]
    thinking_route: Callable[..., Any]
    record_request: Callable[..., None]
    extract_system_prompt: Callable[..., str]
    log_sys_prompt: Callable[..., None]


_deps: AnthropicStreamDeps | None = None

# Back-compat aliases for tests and monkeypatch targets.
_last_resort_call = None
_thinking_route = None
_record_request = None
_extract_system_prompt = None
_log_sys_prompt = None


def inject_deps(
    *,
    last_resort_call,
    thinking_route,
    record_request,
    extract_system_prompt,
    log_sys_prompt,
):
    """Called by server.py to inject functions that live there."""
    global _deps, _last_resort_call, _thinking_route, _record_request
    global _extract_system_prompt, _log_sys_prompt
    _deps = AnthropicStreamDeps(
        last_resort_call=last_resort_call,
        thinking_route=thinking_route,
        record_request=record_request,
        extract_system_prompt=extract_system_prompt,
        log_sys_prompt=log_sys_prompt,
    )
    _last_resort_call = last_resort_call
    _thinking_route = thinking_route
    _record_request = record_request
    _extract_system_prompt = extract_system_prompt
    _log_sys_prompt = log_sys_prompt


def _require_deps() -> AnthropicStreamDeps:
    if _deps is None:
        raise RuntimeError("anthropic_stream.inject_deps must be called before streaming")
    return _deps


async def anthropic_stream_passthrough(body: dict, model: str):
    """含图片时：转发给视觉模型，流式返回。"""
    query_text = ""
    for message in body.get("messages", []):
        content = message.get("content", "")
        if isinstance(content, list):
            query_text = " ".join(block.get("text", "") for block in content if block.get("type") == "text")
        elif isinstance(content, str):
            query_text = content

    content = (
        f"[图片分析] 收到包含图片的请求。当前视觉模型暂未接入，"
        f"请用文字描述图片内容后重新提问。\n\n你的文字描述：{query_text}"
        if query_text
        else "[图片分析] 收到图片请求，请附带文字描述以便分析。"
    )
    async for frame in stream_text_as_sse(content, model, chunk_size=30):
        yield frame


async def anthropic_stream(
    req,
    model: str,
    client_ip: str = "",
    ide_source: str = "",
    sys_prompt_preview: str = "",
):
    """Anthropic SSE stream orchestrator."""
    deps = _require_deps()
    query = extract_query(req.messages)
    t0 = time.time()
    ctx = StreamContext(
        req=req,
        model=model,
        query=query,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
    )

    is_image, _image_prompt = smart_router.detect_image_intent(query)
    if is_image:
        async for frame in stream_image_intent(ctx):
            yield frame
        duration_ms = int((time.time() - t0) * 1000)
        deps.record_request(
            query,
            ctx.backend_used,
            "image_generation",
            duration_ms,
            True,
            client_ip=client_ip,
            ide_source=ide_source,
            sys_prompt_preview=sys_prompt_preview,
        )
        return

    await resolve_thinking(ctx, deps.thinking_route)
    if not ctx.thinking_handled:
        await resolve_normal_route(ctx)
        if ctx.use_speculative:
            async for frame in stream_speculative_path(ctx, last_resort_call=deps.last_resort_call):
                yield frame
            _finalize_request(ctx, query, t0, client_ip, ide_source, sys_prompt_preview, deps)
            _do_logging(req, query, ctx.content, _record_intent(ctx), ctx.backend_used, deps)
            return
        await apply_quality_fallback(ctx)

    if not ctx.content or not ctx.content.strip():
        ctx.content = deps.last_resort_call(messages_to_dicts(req.messages)) or "抱歉，所有后端暂不可用，请稍后重试。"
        ctx.backend_used = ctx.backend_used or "empty_response"

    _finalize_request(ctx, query, t0, client_ip, ide_source, sys_prompt_preview, deps)
    async for frame in stream_text_as_sse(ctx.content, model, chunk_size=20):
        yield frame
    _do_logging(req, query, ctx.content, _record_intent(ctx), ctx.backend_used, deps)


def _record_intent(ctx: StreamContext) -> Any:
    if isinstance(ctx.intent_used, str):
        return ctx.intent_used
    return ctx.intent_name


def _finalize_request(
    ctx: StreamContext,
    query: str,
    t0: float,
    client_ip: str,
    ide_source: str,
    sys_prompt_preview: str,
    deps: AnthropicStreamDeps,
) -> None:
    duration_ms = int((time.time() - t0) * 1000)
    deps.record_request(
        query,
        ctx.backend_used,
        _record_intent(ctx),
        duration_ms,
        True,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
    )


def _do_logging(req, query, content, record_intent, backend_used, deps: AnthropicStreamDeps):
    sys_prompt = deps.extract_system_prompt(req.messages)
    if sys_prompt:
        try:
            deps.log_sys_prompt(sys_prompt)
        except Exception as exc:
            _log.warning("log_sys_prompt failed: %s", type(exc).__name__)
    try:
        if os.environ.get("DISTILL_LOG", "0") == "1":
            smart_router._log_to_distill_queue(query, content, record_intent, backend_used)
    except Exception as exc:
        _log.debug("distill queue log skipped: %s", type(exc).__name__)
