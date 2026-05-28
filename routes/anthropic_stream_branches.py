"""Branch handlers for Anthropic streaming routes (CQ-099)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

import health_tracker
import http_caller
import routing_engine
import smart_router
from orchestrate import orchestrate, needs_orchestration
from response_builder import messages_to_dicts
from routes.anthropic_stream_sse import (
    new_message_id,
    sse_content_block_start,
    sse_message_end,
    sse_message_start,
    sse_text_delta,
    stream_text_as_sse,
)
from routes.images import build_pollinations_url
from routes.quality_gate import (
    default_route,
    get_same_tier_backends,
    get_upgrade_chain,
    quality_check,
    try_backend,
)
from routes.stream_handlers import speculative_stream_chunks

_log = logging.getLogger(__name__)


@dataclass
class StreamContext:
    req: Any
    model: str
    query: str
    ide_source: str
    sys_prompt_preview: str
    complexity: float = 0.5
    intent_used: Any = "unknown"
    intent_name: str = "unknown"
    content: str = ""
    backend_used: str = "unknown"
    thinking_handled: bool = False
    use_speculative: bool = False


async def stream_image_intent(ctx: StreamContext) -> AsyncIterator[str]:
    image_url = build_pollinations_url(ctx.query, "1024x1024")
    content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
    ctx.content = content
    ctx.backend_used = "pollinations"
    async for frame in stream_text_as_sse(content, ctx.model, chunk_size=30):
        yield frame


async def resolve_thinking(ctx: StreamContext, thinking_route) -> None:
    use_thinking = getattr(ctx.req, "thinking", False) or smart_router.detect_thinking_intent(ctx.query)
    if not use_thinking:
        return
    thinking_result = await thinking_route(ctx.query, ctx.req.max_tokens or 4096, ctx.ide_source)
    if not thinking_result:
        return
    ctx.content = thinking_result["answer"]
    ctx.backend_used = thinking_result["backend"]
    ctx.intent_used = "thinking"
    ctx.thinking_handled = True


async def resolve_normal_route(ctx: StreamContext) -> None:
    ctx.intent_used = smart_router.analyze(
        ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source
    )
    ctx.intent_name = (
        ctx.intent_used.get("intent", "unknown")
        if isinstance(ctx.intent_used, dict)
        else "unknown"
    )
    ctx.complexity = (
        ctx.intent_used.get("complexity", 0.5)
        if isinstance(ctx.intent_used, dict)
        else 0.5
    )
    if needs_orchestration(ctx.query, ctx.intent_used):
        result = await asyncio.to_thread(orchestrate, ctx.query)
        ctx.content = result.get("answer", "")
        ctx.backend_used = result.get("backend", "orchestrator")
        ctx.thinking_handled = False
    else:
        ctx.use_speculative = True


async def stream_speculative_path(
    ctx: StreamContext,
    *,
    last_resort_call,
) -> AsyncIterator[str]:
    yield sse_message_start(ctx.model, new_message_id())
    yield sse_content_block_start()

    total_text = ""
    backend_used = "unknown"
    streamed_any = False
    async for chunk_backend, chunk in speculative_stream_chunks(
        ctx.query,
        messages_to_dicts(ctx.req.messages),
        ctx.req.max_tokens or 4096,
        ctx.ide_source,
    ):
        backend_used = chunk_backend
        streamed_any = True
        total_text += chunk
        yield sse_text_delta(chunk)

    if streamed_any and not quality_check(total_text, ctx.complexity, backend_used, query=ctx.query):
        health_tracker.record_response_quality(backend_used, len(total_text), is_error_msg=True)

    if not streamed_any:
        total_text, backend_used = await routing_engine_fallback(ctx, last_resort_call)
        for index in range(0, len(total_text), 30):
            yield sse_text_delta(total_text[index : index + 30])
            await asyncio.sleep(0.01)

    ctx.content = total_text
    ctx.backend_used = backend_used
    stop, delta, end = sse_message_end(len(total_text))
    yield stop
    yield delta
    yield end


async def routing_engine_fallback(ctx: StreamContext, last_resort_call) -> tuple[str, str]:
    try:
        backends = routing_engine.select(
            "ide" if ctx.ide_source else "chat",
            health_tracker.get_health_map(),
        )
        fb_backend, fb_answer, _ = await asyncio.to_thread(
            routing_engine.execute,
            backends,
            lambda b, m, t: http_caller.call_api(
                b, m, t, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source
            ),
            messages_to_dicts(ctx.req.messages),
            ctx.req.max_tokens or 4096,
        )
        fallback_text = fb_answer if fb_answer and fb_backend != "exhausted" else None
    except Exception as exc:
        _log.warning("anthropic stream routing fallback failed: %s", type(exc).__name__, exc_info=True)
        fallback_text = None
        fb_backend = "fallback_error"

    backend_used = fb_backend if fallback_text else "last_resort"
    if fallback_text and not quality_check(fallback_text, ctx.complexity, fb_backend, query=ctx.query):
        health_tracker.record_response_quality(fb_backend, len(fallback_text), is_error_msg=True)
        fallback_text = None
        backend_used = "last_resort"

    if fallback_text:
        return fallback_text, backend_used

    total_text = last_resort_call(messages_to_dicts(ctx.req.messages)) or "抱歉，所有后端暂不可用，请稍后重试。"
    return total_text, backend_used


async def apply_quality_fallback(ctx: StreamContext) -> None:
    if quality_check(ctx.content, ctx.complexity, ctx.backend_used, query=ctx.query):
        return
    fallback_backend = (
        default_route(ctx.query, ctx.ide_source)
        if ctx.backend_used == "unknown"
        else ctx.backend_used
    )
    for alt in get_same_tier_backends(fallback_backend):
        alt_result = await try_backend(
            alt,
            ctx.query,
            ctx.req.max_tokens or 4096,
            messages=messages_to_dicts(ctx.req.messages),
        )
        if alt_result and quality_check(alt_result["answer"], ctx.complexity, alt, query=ctx.query):
            ctx.content = alt_result["answer"]
            ctx.backend_used = alt
            return
    for upgraded in get_upgrade_chain(fallback_backend):
        up_result = await try_backend(
            upgraded,
            ctx.query,
            ctx.req.max_tokens or 4096,
            messages=messages_to_dicts(ctx.req.messages),
        )
        if up_result and quality_check(up_result["answer"], ctx.complexity, upgraded, query=ctx.query):
            ctx.content = up_result["answer"]
            ctx.backend_used = upgraded
            return
    if not ctx.content:
        ctx.content = "抱歉，所有后端暂不可用，请稍后重试。"
        ctx.backend_used = "fallback_exhausted"
