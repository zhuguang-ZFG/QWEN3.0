"""Main chat request handler (CQ-014 slice 4/12)."""

from __future__ import annotations

from typing import Callable

from fastapi import HTTPException

from chat_models import ChatRequest
from orchestrate import needs_orchestration as needs_orchestration
from response_builder import extract_query
from routes.chat_fallback import inject_deps as _inject_chat_fallback_deps
from routes.quality_gate import quality_check as quality_check
from routes.v3_adapters import v3_route as v3_route
from routes.chat_handler_dispatch import (
    build_streaming_response,
    execute_non_stream_route,
    finalize_success_response,
    maybe_image_response,
    maybe_thinking_response,
    start_chat_run,
)

_model_id = "lima-1.3"
_record_request: Callable[..., None] = lambda *a, **kw: None
_record_fallback: Callable[..., None] | None = None
_build_pollinations_url: Callable[[str, str], str] | None = None


def inject_deps(
    *,
    model_id: str,
    record_request: Callable[..., None],
    record_fallback: Callable[..., None],
    build_pollinations_url: Callable[[str, str], str],
) -> None:
    global _model_id, _record_request, _record_fallback, _build_pollinations_url
    _model_id = model_id
    _record_request = record_request
    _record_fallback = record_fallback
    _build_pollinations_url = build_pollinations_url
    _inject_chat_fallback_deps(
        model_id=model_id,
        record_request=record_request,
        record_fallback=record_fallback,
    )


async def handle_chat(
    req: ChatRequest,
    fmt: str = "openai",
    request_model: str | None = None,
    client_ip: str = "",
    ide_source: str = "",
    sys_prompt_preview: str = "",
    request_headers: dict | None = None,
):
    query = extract_query(req.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    try:
        from context_pipeline.tracing import new_trace

        trace = new_trace()
        trace.start_span("handle_chat", ide=ide_source)
    except ImportError:
        trace = None

    ctx = start_chat_run(
        req,
        fmt=fmt,
        request_model=request_model,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
        request_headers=request_headers,
        trace=trace,
    )

    image_resp = await maybe_image_response(
        ctx,
        req,
        model_id=_model_id,
        record_request=_record_request,
        build_pollinations_url=_build_pollinations_url,
    )
    if image_resp is not None:
        return image_resp

    thinking_resp = await maybe_thinking_response(
        ctx,
        req,
        model_id=_model_id,
        record_request=_record_request,
    )
    if thinking_resp is not None:
        return thinking_resp

    if req.stream:
        return build_streaming_response(ctx, req)

    result, intent = await execute_non_stream_route(ctx, req)
    return await finalize_success_response(
        ctx,
        req,
        result,
        intent,
        model_id=_model_id,
        record_request=_record_request,
    )
