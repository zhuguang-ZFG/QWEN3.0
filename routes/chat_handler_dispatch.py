"""Non-stream chat dispatch helpers (CQ-014 slice 12)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

from fastapi.responses import JSONResponse, StreamingResponse

import routing_intent
from chat_models import ChatRequest
from context_pipeline.tracing import get_current_trace
from routes.v3_adapters import v3_route
from response_builder import (
    build_anthropic_response,
    build_response,
    extract_query,
    make_chat_id,
)

_log = logging.getLogger(__name__)
from routes.chat_preflight import ChatPreflightResult, prepare_chat_preflight
from routes.chat_stream import build_stream_chunk, stream_response
from routes.chat_support import attach_memory_recall_meta, thinking_route
from routes.request_tracking import resolve_ip_country


def _chat_handler():
    import routes.chat_handler as mod

    return mod


@dataclass
class RoutePrefs:
    prefer: str | None
    ide_source: str
    use_thinking: bool


@dataclass
class ChatRunContext:
    chat_id: str
    query: str
    t0: float
    fmt: str
    request_model: str | None
    client_ip: str
    ide_source: str
    sys_prompt_preview: str
    memory_recall_meta: dict
    memory_session_id: str | None
    preflight: ChatPreflightResult
    prefs: RoutePrefs


def resolve_route_prefs(req: ChatRequest, ide_source: str, query: str) -> RoutePrefs:
    prefer = None
    ide = ide_source
    if req.model in ("fast", "lima"):
        prefer = "longcat_lite"
    elif req.model in ("expert", "lima-thinking"):
        prefer = "scnet_ds_pro"
        req.thinking = True
    elif req.model == "code":
        ide = ide or "chat_code_mode"
        prefer = "scnet_qwen235b"

    # Claude Code sends full history every turn and needs a large context window.
    # SCNet DS Pro: 64K context, free, unlimited (safer than web reverse proxies)
    if ide_source and "claude" in ide_source.lower():
        prefer = prefer or "scnet_ds_pro"

    use_thinking = getattr(req, "thinking", False) or routing_intent.detect_thinking_intent(query)
    return RoutePrefs(prefer=prefer, ide_source=ide, use_thinking=use_thinking)


def start_chat_run(
    req: ChatRequest,
    *,
    fmt: str,
    request_model: str | None,
    client_ip: str,
    ide_source: str,
    sys_prompt_preview: str,
    request_headers: dict | None,
    trace,
) -> ChatRunContext:
    query = extract_query(req.messages)
    preflight = prepare_chat_preflight(
        req,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
        request_headers=request_headers,
        trace=trace,
    )
    prefs = resolve_route_prefs(req, ide_source, query)
    return ChatRunContext(
        chat_id=make_chat_id(),
        query=query,
        t0=time.time(),
        fmt=fmt,
        request_model=request_model,
        client_ip=client_ip,
        ide_source=prefs.ide_source,
        sys_prompt_preview=preflight.system_prompt,
        memory_recall_meta=preflight.memory_recall_meta,
        memory_session_id=preflight.memory_session_id,
        preflight=preflight,
        prefs=prefs,
    )


async def maybe_image_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    *,
    model_id: str,
    record_request: Callable[..., None],
    build_pollinations_url: Callable[[str, str], str] | None,
) -> JSONResponse | StreamingResponse | None:
    is_image, image_prompt = routing_intent.detect_image_intent(ctx.query)
    if not is_image or not build_pollinations_url:
        return None
    image_url = build_pollinations_url(image_prompt, "1024x1024")
    content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
    duration_ms = int((time.time() - ctx.t0) * 1000)
    country = await resolve_ip_country(ctx.client_ip)
    record_request(
        ctx.query,
        "pollinations",
        "image_generation",
        duration_ms,
        True,
        client_ip=ctx.client_ip,
        ide_source=ctx.ide_source,
        sys_prompt_preview=ctx.sys_prompt_preview,
        country=country,
    )
    # Streaming: return SSE-formatted response so stream-parsing clients work
    if req.stream:

        async def _image_sse():
            yield build_stream_chunk(ctx.chat_id, content)
            yield build_stream_chunk(ctx.chat_id, "", finish=True)
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _image_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    if ctx.fmt == "anthropic":
        return JSONResponse(
            build_anthropic_response(ctx.chat_id, content, "pollinations", ctx.request_model or model_id)
        )
    return JSONResponse(build_response(ctx.chat_id, content, "pollinations", duration_ms))


async def maybe_thinking_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    *,
    model_id: str,
    record_request: Callable[..., None],
) -> JSONResponse | None:
    if not ctx.prefs.use_thinking or req.stream:
        return None
    thinking_result = await thinking_route(ctx.query, req.max_tokens or 4096, ctx.ide_source)
    if not thinking_result:
        return None
    content = thinking_result["answer"]
    backend = thinking_result["backend"]
    duration_ms = int((time.time() - ctx.t0) * 1000)
    country = await resolve_ip_country(ctx.client_ip)
    record_request(
        ctx.query,
        backend,
        "thinking",
        duration_ms,
        True,
        client_ip=ctx.client_ip,
        ide_source=ctx.ide_source,
        sys_prompt_preview=ctx.sys_prompt_preview,
        country=country,
    )
    if ctx.fmt == "anthropic":
        return JSONResponse(build_anthropic_response(ctx.chat_id, content, backend, ctx.request_model or model_id))
    resp = build_response(ctx.chat_id, content, backend, duration_ms)
    resp["choices"][0]["message"]["thinking"] = True
    resp["x_lima_meta"]["thinking_mode"] = True
    return JSONResponse(attach_memory_recall_meta(resp, ctx.memory_recall_meta))


def build_streaming_response(ctx: ChatRunContext, req: ChatRequest) -> StreamingResponse:
    routing_intent.analyze_intent(ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source)
    _chat_handler()  # ensures chat_handler deps are imported/injected
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    trace = get_current_trace()
    if trace is not None:
        headers["X-LiMa-Trace-Id"] = trace.trace_id
    return StreamingResponse(
        stream_response(
            ctx.chat_id,
            ctx.query,
            False,
            ide_source=ctx.ide_source,
            sys_prompt_preview=ctx.sys_prompt_preview,
            use_thinking=ctx.prefs.use_thinking,
            messages=ctx.preflight.prompt_context_messages,
            prefer=ctx.prefs.prefer,
        ),
        media_type="text/event-stream",
        headers=headers,
    )


async def execute_non_stream_route(ctx: ChatRunContext, req: ChatRequest) -> tuple[dict, dict]:
    intent = routing_intent.analyze_intent(ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source)
    _chat_handler()  # ensures chat_handler deps are imported/injected
    result = await asyncio.to_thread(
        v3_route,
        ctx.query,
        ctx.preflight.request_messages,
        system_prompt=ctx.sys_prompt_preview,
        ide=ctx.ide_source,
        max_tokens=req.max_tokens or 4096,
        needs_tools=req.has_tools,
        tools=req.tools,
        prefer=ctx.prefs.prefer,
    )
    return result, intent if isinstance(intent, dict) else {}
