"""Non-stream chat dispatch helpers (CQ-014 slice 12)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi.responses import JSONResponse, StreamingResponse

import routing_facade
from chat_models import ChatRequest, extract_system_prompt
from chat_request_utils import request_sampling_params
from http_errors import BackendError
from opencode_config import OPENCODE_DIRECT_STREAM, OPENCODE_PREFERRED_BACKEND
from orchestrate import orchestrate
from response_builder import (
    build_anthropic_response,
    build_response,
    extract_query,
    make_chat_id,
)
from routes.chat_fallback import QualityFallbackRequest, resolve_quality_fallback

_log = logging.getLogger(__name__)
from routes.chat_non_stream import execute_non_stream_route
from routes.chat_post_closeout import (
    finalize_success_response,
    maybe_log_distill_queue,
    persist_session_memory,
    record_capability_evidence,
    record_chat_observability,
)
from routes.chat_preflight import ChatPreflightResult, prepare_chat_preflight
from routes.chat_stream import stream_response
from routes.chat_support import attach_lima_meta, attach_memory_recall_meta, log_sys_prompt, thinking_route


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
    user_agent: str
    ide_source: str
    sys_prompt_preview: str
    memory_recall_meta: dict
    memory_session_id: str | None
    preflight: ChatPreflightResult
    prefs: RoutePrefs
    request_headers: dict | None = None


def resolve_route_prefs(req: ChatRequest, ide_source: str, query: str) -> RoutePrefs:
    prefer = None
    ide = ide_source
    if req.model in ("fast", "lima"):
        prefer = "longcat_lite"
    elif req.model in ("expert", "lima-thinking"):
        prefer = "scnet_ds_pro"
        req.thinking = True
    elif req.model == "lima":
        ide = ide or "chat_code_mode"
        prefer = "scnet_qwen235b"

    # Claude Code sends full history every turn → needs large context
    # SCNet DS Pro: 64K context, free, unlimited (safer than web reverse proxies)
    if ide_source and "claude" in ide_source.lower():
        prefer = prefer or "scnet_ds_pro"

    # OpenCode sends full context like Claude Code → needs large context window
    # Override fast model default (longcat_lite) for OpenCode — it needs tool-capable backends
    if ide_source and "opencode" in ide_source.lower():
        if prefer in (None, "longcat_lite"):
            prefer = OPENCODE_PREFERRED_BACKEND

    use_thinking = getattr(req, "thinking", False) or routing_facade.detect_thinking_intent(query)
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
    user_agent = (request_headers or {}).get("user-agent", "")
    return ChatRunContext(
        chat_id=make_chat_id(),
        query=query,
        t0=time.time(),
        fmt=fmt,
        request_model=request_model,
        client_ip=client_ip,
        user_agent=user_agent,
        ide_source=prefs.ide_source,
        sys_prompt_preview=preflight.system_prompt,
        memory_recall_meta=preflight.memory_recall_meta,
        memory_session_id=preflight.memory_session_id,
        preflight=preflight,
        prefs=prefs,
        request_headers=request_headers,
    )


async def maybe_image_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    *,
    model_id: str,
    record_request: Callable[..., None],
    build_pollinations_url: Callable[[str, str], str] | None,
) -> JSONResponse | None:
    is_image, image_prompt = routing_facade.detect_image_intent(ctx.query)
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
    is_opencode = bool(
        ctx.ide_source and "opencode" in ctx.ide_source.lower()
    )
    if (
        OPENCODE_DIRECT_STREAM
        and is_opencode
        and ctx.prefs.prefer
    ):
        from routes.opencode_direct_stream import (
            resolve_opencode_backend,
            stream_openai_passthrough,
        )

        backend = resolve_opencode_backend(ctx.prefs.prefer, require_tools=req.has_tools)

        async def _opencode_tool_stream():
            synthetic = _maybe_synthetic_tool_call(ctx.chat_id, req, ctx.query)
            if synthetic is not None:
                for line in synthetic:
                    yield line
                return
            streamed_any = False
            try:
                async for line in stream_openai_passthrough(
                    backend=backend,
                    messages=ctx.preflight.prompt_context_messages,
                    chat_id=ctx.chat_id,
                    model=ctx.request_model or _model_id_fallback(),
                    tools=req.tools,
                    tool_choice=req.tool_choice,
                    max_tokens=req.max_tokens or 4096,
                    system_prompt=ctx.preflight.system_prompt,
                    ide=ctx.ide_source,
                    reasoning_effort=req.reasoning_effort,
                    sampling=request_sampling_params(req),
                    request_headers=ctx.request_headers,
                ):
                    streamed_any = True
                    yield line
            except BackendError as exc:
                if not streamed_any:
                    _log.debug(
                        "opencode direct stream failed before first chunk; falling back: %s",
                        type(exc).__name__,
                    )
                    async for line in stream_response(
                        ctx.chat_id,
                        ctx.query,
                        False,
                        ide_source=ctx.ide_source,
                        sys_prompt_preview=ctx.sys_prompt_preview,
                        use_thinking=ctx.prefs.use_thinking,
                        messages=ctx.preflight.prompt_context_messages,
                        prefer=ctx.prefs.prefer,
                        model=ctx.request_model or "",
                        reasoning_effort=req.reasoning_effort,
                        sampling=request_sampling_params(req),
                        has_tools=False,
                    ):
                        yield line
                    return
                yield _build_opencode_stream_error_chunk(exc)
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _opencode_tool_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    intent = routing_facade.analyze(
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
            model=ctx.request_model or "",
            reasoning_effort=req.reasoning_effort,
            has_tools=req.has_tools,
            sampling=request_sampling_params(req),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _model_id_fallback() -> str:
    try:
        from chat_models import MODEL_ID
        return MODEL_ID
    except ImportError:
        return "lima-1.3"


def _build_opencode_stream_error_chunk(exc: BackendError) -> str:
    message = str(exc) or "Backend stream failed"
    payload = {
        "type": "error",
        "error": {
            "code": "server_is_overloaded",
            "message": message,
            "type": "api_error",
        },
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _maybe_synthetic_tool_call(
    chat_id: str,
    req: ChatRequest,
    query: str,
) -> list[str] | None:
    tool = _resolve_requested_tool(req, query)
    if tool is None:
        return None
    name = tool.get("name", "")
    if not name:
        return None
    arguments = _infer_tool_arguments(query, tool.get("parameters", {}))
    tool_call = {
        "index": 0,
        "id": f"call_{chat_id[-12:]}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }
    start = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "model": req.model or _model_id_fallback(),
        "choices": [{"index": 0, "delta": {"tool_calls": [tool_call]}, "finish_reason": None}],
    }
    finish = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "model": req.model or _model_id_fallback(),
        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
    }
    return [
        f"data: {json.dumps(start, ensure_ascii=False)}\n\n",
        f"data: {json.dumps(finish, ensure_ascii=False)}\n\n",
        "data: [DONE]\n\n",
    ]


def _resolve_requested_tool(req: ChatRequest, query: str) -> dict | None:
    tools = [
        t.get("function", {})
        for t in (req.tools or [])
        if isinstance(t, dict) and isinstance(t.get("function"), dict)
    ]
    if not tools:
        return None
    if isinstance(req.tool_choice, dict):
        forced_name = ((req.tool_choice.get("function") or {}).get("name") or "").lower()
        for tool in tools:
            if tool.get("name", "").lower() == forced_name:
                return tool
    lowered = query.lower()
    for tool in tools:
        name = tool.get("name", "")
        if name and re.search(rf"\b(use|call|run)\s+(?:the\s+tool\s+)?{re.escape(name.lower())}\b", lowered):
            return tool
    return None


def _infer_tool_arguments(query: str, parameters: dict) -> dict:
    props = parameters.get("properties", {}) if isinstance(parameters, dict) else {}
    required = parameters.get("required", []) if isinstance(parameters, dict) else []
    args: dict[str, str] = {}
    for name in required:
        if name not in props:
            continue
        lname = name.lower()
        if lname in ("city", "location"):
            args[name] = _extract_location_argument(query)
        elif lname in ("path", "file", "file_path", "filename"):
            args[name] = _extract_file_argument(query)
    return {k: v for k, v in args.items() if v}


def _extract_location_argument(query: str) -> str:
    match = re.search(r"\b(?:for|in|city)\s+([A-Z][A-Za-z ._-]{1,40})", query)
    if not match:
        return ""
    value = match.group(1)
    return re.split(r"\b(now|today|using|with|do not|please)\b|[.?!,]", value, 1)[0].strip()


def _extract_file_argument(query: str) -> str:
    match = re.search(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)", query)
    return match.group(1) if match else ""


async def execute_non_stream_route(ctx: ChatRunContext, req: ChatRequest) -> tuple[dict, dict]:
    """Re-exported from routes.chat_non_stream for backward compat."""
    from routes.chat_non_stream import execute_non_stream_route as _impl
    return await _impl(ctx, req)


async def finalize_success_response(
    ctx: ChatRunContext, req: ChatRequest, result: dict, intent: dict,
    *, model_id: str, record_request,
):
    """Re-exported from routes.chat_post_closeout for backward compat."""
    from routes.chat_post_closeout import finalize_success_response as _impl
    return await _impl(ctx, req, result, intent, model_id=model_id, record_request=record_request)
