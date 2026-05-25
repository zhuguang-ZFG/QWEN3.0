"""Main chat request handler (CQ-014 slice 4)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Callable

from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

import smart_router
from chat_models import ChatRequest, extract_system_prompt
from orchestrate import needs_orchestration, orchestrate
from response_builder import (
    build_anthropic_response,
    build_response,
    extract_query,
    make_chat_id,
    messages_to_dicts,
)
from routes.quality_gate import quality_check
from routes.v3_adapters import v3_route
from server_context import build_prompt_context, messages_with_system_context

from routes.chat_fallback import QualityFallbackRequest, inject_deps as _inject_chat_fallback_deps, resolve_quality_fallback
from routes.chat_stream import stream_response
from routes.chat_support import attach_memory_recall_meta, log_sys_prompt, thinking_route

_model_id = "lima-1.3"
_record_request: Callable[..., None] | None = None
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
        from context_pipeline.guardrails import GuardrailSeverity, run_input_guardrails

        raw_messages = [
            {"role": m.role, "content": m.content} if hasattr(m, "role") else m
            for m in req.messages
        ]
        guard_result = run_input_guardrails(raw_messages)
        if not guard_result.passed and guard_result.severity == GuardrailSeverity.BLOCK:
            raise HTTPException(status_code=422, detail=f"Input blocked: {guard_result.violations}")
    except ImportError:
        pass

    chat_id = make_chat_id()
    t0 = time.time()

    try:
        from context_pipeline.tracing import new_trace

        trace = new_trace()
        trace.start_span("handle_chat", chat_id=chat_id, ide=ide_source)
    except ImportError:
        trace = None

    prompt_ctx = build_prompt_context(
        req,
        system_prompt=extract_system_prompt(req.messages) or sys_prompt_preview or "",
        request_headers=request_headers,
        client_ip=client_ip,
        ide_source=ide_source,
        trace=trace,
    )
    request_messages = prompt_ctx.request_messages
    prompt_context_messages = prompt_ctx.prompt_context_messages
    sys_prompt_preview = prompt_ctx.system_prompt
    memory_recall_meta = prompt_ctx.memory_recall_meta
    memory_session_id = prompt_ctx.memory_session_id

    try:
        from context_pipeline.token_budget import check_budget

        budget_status = check_budget(
            request_messages,
            sys_prompt_preview or "",
            "coding" if ide_source else "chat",
        )
        if not budget_status["within_budget"] and budget_status["action"] == "truncate_context":
            if len(req.messages) > 10:
                req.messages = req.messages[:3] + req.messages[-7:]
                request_messages = messages_to_dicts(req.messages)
                prompt_context_messages = messages_with_system_context(
                    request_messages, sys_prompt_preview
                )
    except ImportError:
        pass

    try:
        from user_identity.adapter import adapt_system_prompt

        adapted = adapt_system_prompt(sys_prompt_preview or "", client_ip)
        if adapted != sys_prompt_preview:
            sys_prompt_preview = adapted
            prompt_context_messages = messages_with_system_context(
                request_messages, sys_prompt_preview
            )
    except ImportError:
        pass

    prefer = None
    if req.model in ("fast", "lima"):
        prefer = "longcat_lite"
    elif req.model in ("expert", "lima-thinking"):
        prefer = "scnet_ds_pro"
        req.thinking = True
    elif req.model in ("code", "lima-code"):
        prefer = None
        ide_source = ide_source or "chat_code_mode"
    elif req.model == "vision":
        prefer = None

    is_image, image_prompt = smart_router.detect_image_intent(query)
    if is_image and _build_pollinations_url:
        image_url = _build_pollinations_url(image_prompt, "1024x1024")
        content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
        duration_ms = int((time.time() - t0) * 1000)
        _record_request(
            query,
            "pollinations",
            "image_generation",
            duration_ms,
            True,
            client_ip=client_ip,
            ide_source=ide_source,
            sys_prompt_preview=sys_prompt_preview,
        )
        if fmt == "anthropic":
            return JSONResponse(
                build_anthropic_response(chat_id, content, "pollinations", request_model or _model_id)
            )
        return JSONResponse(build_response(chat_id, content, "pollinations", duration_ms))

    use_thinking = getattr(req, "thinking", False) or smart_router.detect_thinking_intent(query)
    if use_thinking and not req.stream:
        thinking_result = await thinking_route(query, req.max_tokens or 4096, ide_source)
        if thinking_result:
            content = thinking_result["answer"]
            backend = thinking_result["backend"]
            duration_ms = int((time.time() - t0) * 1000)
            _record_request(
                query,
                backend,
                "thinking",
                duration_ms,
                True,
                client_ip=client_ip,
                ide_source=ide_source,
                sys_prompt_preview=sys_prompt_preview,
            )
            if fmt == "anthropic":
                return JSONResponse(
                    build_anthropic_response(chat_id, content, backend, request_model or _model_id)
                )
            resp = build_response(chat_id, content, backend, duration_ms)
            resp["choices"][0]["message"]["thinking"] = True
            resp["x_lima_meta"]["thinking_mode"] = True
            return JSONResponse(attach_memory_recall_meta(resp, memory_recall_meta))

    intent = smart_router.analyze(query, system_prompt=sys_prompt_preview, ide=ide_source)
    use_orchestration = needs_orchestration(query, intent) if not prefer else False

    if req.stream:
        return StreamingResponse(
            stream_response(
                chat_id,
                query,
                use_orchestration,
                ide_source=ide_source,
                sys_prompt_preview=sys_prompt_preview,
                use_thinking=use_thinking,
                messages=prompt_context_messages,
                prefer=prefer,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, query)
    else:
        result = await asyncio.to_thread(
            v3_route,
            query,
            request_messages,
            system_prompt=sys_prompt_preview,
            ide=ide_source,
            max_tokens=req.max_tokens or 4096,
        )

    content = result.get("answer", "")
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    intent_name = intent.get("intent", "unknown") if isinstance(intent, dict) else "unknown"
    complexity = intent.get("complexity", 0.5) if isinstance(intent, dict) else 0.5

    if not quality_check(content, complexity, backend, query=query):
        return await resolve_quality_fallback(
            QualityFallbackRequest(
                chat_id=chat_id,
                query=query,
                content=content,
                backend=backend,
                complexity=complexity,
                intent_name=intent_name,
                fmt=fmt,
                request_model=request_model,
                max_tokens=req.max_tokens or 1024,
                ide_source=ide_source,
                client_ip=client_ip,
                sys_prompt_preview=sys_prompt_preview,
                prompt_context_messages=prompt_context_messages,
                memory_recall_meta=memory_recall_meta,
                elapsed_ms=int((time.time() - t0) * 1000),
            )
        )

    duration_ms = int((time.time() - t0) * 1000)

    try:
        from session_memory.compactor import compact_session, needs_compaction
        from session_memory.store import save_memory
        import hashlib

        session_id = memory_session_id or hashlib.md5((client_ip or "anon").encode()).hexdigest()[:12]
        save_memory(session_id, "user", query[:100])
        if content:
            save_memory(session_id, "assistant", content[:100])
        if needs_compaction(session_id):
            compact_session(session_id)
    except (ImportError, Exception):
        pass

    _record_request(
        query,
        backend,
        intent_name,
        duration_ms,
        True,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
    )

    try:
        from observability.correlation import record_request_correlation

        record_request_correlation(
            request_id=chat_id,
            backend=backend,
            status="success",
            latency_ms=duration_ms,
        )
    except ImportError:
        pass

    try:
        if os.environ.get("DISTILL_LOG", "0") == "1":
            smart_router._log_to_distill_queue(query, content, intent_name, backend)
    except Exception:
        pass

    sys_prompt = extract_system_prompt(req.messages)
    if sys_prompt:
        try:
            log_sys_prompt(sys_prompt)
        except Exception:
            pass

    if fmt == "anthropic":
        return JSONResponse(
            build_anthropic_response(chat_id, content, backend, request_model or _model_id)
        )
    return JSONResponse(
        attach_memory_recall_meta(
            build_response(chat_id, content, backend, total_ms),
            memory_recall_meta,
        )
    )
