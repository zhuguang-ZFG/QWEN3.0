"""Non-stream chat dispatch helpers (CQ-014 slice 12)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

from fastapi.responses import JSONResponse, StreamingResponse

import smart_router
from chat_models import ChatRequest, extract_system_prompt
from orchestrate import orchestrate
from response_builder import (
    build_anthropic_response,
    build_response,
    extract_query,
    make_chat_id,
)
from routes.chat_fallback import QualityFallbackRequest, resolve_quality_fallback

_log = logging.getLogger(__name__)
from routes.chat_post_closeout import (
    maybe_log_distill_queue,
    persist_session_memory,
    record_capability_evidence,
    record_chat_observability,
)
from routes.chat_preflight import ChatPreflightResult, prepare_chat_preflight
from routes.chat_stream import stream_response
from routes.chat_support import attach_memory_recall_meta, log_sys_prompt, thinking_route

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
    elif req.model in ("code", "lima-code"):
        ide = ide or "chat_code_mode"
        prefer = "scnet_qwen235b"

    # Claude Code sends full history every turn → needs large context
    # SCNet DS Pro: 64K context, free, unlimited (safer than web reverse proxies)
    if ide_source and "claude" in ide_source.lower():
        prefer = prefer or "scnet_ds_pro"

    use_thinking = getattr(req, "thinking", False) or smart_router.detect_thinking_intent(query)
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
) -> JSONResponse | None:
    is_image, image_prompt = smart_router.detect_image_intent(ctx.query)
    if not is_image or not build_pollinations_url:
        return None
    image_url = build_pollinations_url(image_prompt, "1024x1024")
    content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
    duration_ms = int((time.time() - ctx.t0) * 1000)
    record_request(
        ctx.query,
        "pollinations",
        "image_generation",
        duration_ms,
        True,
        client_ip=ctx.client_ip,
        ide_source=ctx.ide_source,
        sys_prompt_preview=ctx.sys_prompt_preview,
    )
    if ctx.fmt == "anthropic":
        return JSONResponse(
            build_anthropic_response(
                ctx.chat_id, content, "pollinations", ctx.request_model or model_id
            )
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
    thinking_result = await thinking_route(
        ctx.query, req.max_tokens or 4096, ctx.ide_source
    )
    if not thinking_result:
        return None
    content = thinking_result["answer"]
    backend = thinking_result["backend"]
    duration_ms = int((time.time() - ctx.t0) * 1000)
    record_request(
        ctx.query,
        backend,
        "thinking",
        duration_ms,
        True,
        client_ip=ctx.client_ip,
        ide_source=ctx.ide_source,
        sys_prompt_preview=ctx.sys_prompt_preview,
    )
    if ctx.fmt == "anthropic":
        return JSONResponse(
            build_anthropic_response(
                ctx.chat_id, content, backend, ctx.request_model or model_id
            )
        )
    resp = build_response(ctx.chat_id, content, backend, duration_ms)
    resp["choices"][0]["message"]["thinking"] = True
    resp["x_lima_meta"]["thinking_mode"] = True
    return JSONResponse(attach_memory_recall_meta(resp, ctx.memory_recall_meta))


def build_streaming_response(ctx: ChatRunContext, req: ChatRequest) -> StreamingResponse:
    intent = smart_router.analyze(
        ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source
    )
    handler = _chat_handler()
    use_orchestration = (
        handler.needs_orchestration(ctx.query, intent)
        if not ctx.prefs.prefer
        else False
    )
    return StreamingResponse(
        stream_response(
            ctx.chat_id,
            ctx.query,
            use_orchestration,
            ide_source=ctx.ide_source,
            sys_prompt_preview=ctx.sys_prompt_preview,
            use_thinking=ctx.prefs.use_thinking,
            messages=ctx.preflight.prompt_context_messages,
            prefer=ctx.prefs.prefer,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def execute_non_stream_route(ctx: ChatRunContext, req: ChatRequest) -> tuple[dict, dict]:
    intent = smart_router.analyze(
        ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source
    )
    handler = _chat_handler()
    use_orchestration = (
        handler.needs_orchestration(ctx.query, intent)
        if not ctx.prefs.prefer
        else False
    )
    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, ctx.query)
    else:
        result = await asyncio.to_thread(
            handler.v3_route,
            ctx.query,
            ctx.preflight.request_messages,
            system_prompt=ctx.sys_prompt_preview,
            ide=ctx.ide_source,
            max_tokens=req.max_tokens or 4096,
            needs_tools=req.has_tools,
            tools=req.tools,
        )
    return result, intent if isinstance(intent, dict) else {}


async def finalize_success_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    result: dict,
    intent: dict,
    *,
    model_id: str,
    record_request: Callable[..., None],
) -> JSONResponse:
    content = result.get("answer", "")
    from response_cleaner import clean_response
    content = clean_response(content, result.get("backend", "")) or content
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    intent_name = intent.get("intent", "unknown")
    complexity = intent.get("complexity", 0.5)

    if not _chat_handler().quality_check(content, complexity, backend, query=ctx.query):
        return await resolve_quality_fallback(
            QualityFallbackRequest(
                chat_id=ctx.chat_id,
                query=ctx.query,
                content=content,
                backend=backend,
                complexity=complexity,
                intent_name=intent_name,
                fmt=ctx.fmt,
                request_model=ctx.request_model,
                max_tokens=req.max_tokens or 1024,
                ide_source=ctx.ide_source,
                client_ip=ctx.client_ip,
                sys_prompt_preview=ctx.sys_prompt_preview,
                prompt_context_messages=ctx.preflight.prompt_context_messages,
                memory_recall_meta=ctx.memory_recall_meta,
                elapsed_ms=int((time.time() - ctx.t0) * 1000),
            )
        )

    duration_ms = int((time.time() - ctx.t0) * 1000)
    persist_session_memory(
        client_ip=ctx.client_ip,
        memory_session_id=ctx.memory_session_id,
        query=ctx.query,
        content=content,
    )
    record_request(
        ctx.query,
        backend,
        intent_name,
        duration_ms,
        True,
        client_ip=ctx.client_ip,
        ide_source=ctx.ide_source,
        sys_prompt_preview=ctx.sys_prompt_preview,
    )
    record_chat_observability(
        chat_id=ctx.chat_id, backend=backend, duration_ms=duration_ms
    )
    record_capability_evidence(
        request_id=ctx.chat_id,
        backend=backend,
        fallback_used=bool(result.get("fallback_used")),
        latency_ms=duration_ms,
        status="ok",
    )
    maybe_log_distill_queue(
        query=ctx.query, content=content, intent=intent_name, backend=backend
    )

    sys_prompt = extract_system_prompt(req.messages)
    if sys_prompt:
        try:
            log_sys_prompt(sys_prompt)
        except Exception as exc:
            _log.warning(
                "log_sys_prompt failed: %s",
                type(exc).__name__,
                exc_info=True,
            )

    if ctx.fmt == "anthropic":
        return JSONResponse(
            build_anthropic_response(
                ctx.chat_id, content, backend, ctx.request_model or model_id
            )
        )
    return JSONResponse(
        attach_memory_recall_meta(
            build_response(ctx.chat_id, content, backend, total_ms),
            ctx.memory_recall_meta,
        )
    )
