"""Non-stream chat response closeout helpers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Protocol

from fastapi.responses import JSONResponse

from chat_models import ChatRequest, extract_system_prompt
from response_builder import build_anthropic_response, build_response
from response_cleaner import clean_response
from routes.chat_handler_dispatch import ChatRunContext
from context_pipeline.tracing import get_current_trace
from routes.chat_post_closeout import (
    maybe_log_distill_queue,
    persist_session_memory,
    record_capability_evidence,
    record_chat_observability,
)
from routes.chat_support import attach_memory_recall_meta, log_sys_prompt
from routes.request_tracking import resolve_ip_country

_log = logging.getLogger(__name__)


class RecordRequestFunc(Protocol):
    def __call__(
        self,
        query: str,
        backend: str,
        intent: str,
        duration_ms: int,
        success: bool,
        *,
        client_ip: str = "",
        ide_source: str = "",
        sys_prompt_preview: str = "",
        country: str = "",
    ) -> None: ...


def _safe_side_effect(label: str, fn: Callable[..., None], /, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        _log.warning("%s failed: %s", label, type(exc).__name__, exc_info=True)


def _safe_record_request(
    record_request: RecordRequestFunc,
    ctx: ChatRunContext,
    backend: str,
    intent_name: str,
    duration_ms: int,
    country: str = "",
) -> None:
    _safe_side_effect(
        "record_request",
        record_request,
        ctx.query,
        backend,
        intent_name,
        duration_ms,
        True,
        client_ip=ctx.client_ip,
        ide_source=ctx.ide_source,
        sys_prompt_preview=ctx.sys_prompt_preview,
        country=country,
    )


def _fire_side_effects(
    ctx: ChatRunContext,
    req: ChatRequest,
    content: str,
    backend: str,
    intent_name: str,
    duration_ms: int,
    record_request: RecordRequestFunc,
    result: dict,
    country: str = "",
) -> None:
    """Fire all post-response side effects (memory, observability, evidence, logging)."""
    _safe_side_effect(
        "persist_session_memory",
        persist_session_memory,
        client_ip=ctx.client_ip,
        memory_session_id=ctx.memory_session_id,
        query=ctx.query,
        content=content,
    )
    _safe_record_request(record_request, ctx, backend, intent_name, duration_ms, country=country)
    _safe_side_effect(
        "record_chat_observability",
        record_chat_observability,
        chat_id=ctx.chat_id,
        backend=backend,
        duration_ms=duration_ms,
    )
    _safe_side_effect(
        "record_capability_evidence",
        record_capability_evidence,
        request_id=ctx.chat_id,
        backend=backend,
        fallback_used=bool(result.get("fallback_used")),
        latency_ms=duration_ms,
        status="ok",
    )
    _safe_side_effect(
        "maybe_log_distill_queue",
        maybe_log_distill_queue,
        query=ctx.query,
        content=content,
        intent=intent_name,
        backend=backend,
    )
    _log_system_prompt(req)


async def finalize_success_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    result: dict,
    intent: dict,
    *,
    model_id: str,
    record_request: RecordRequestFunc,
) -> JSONResponse:
    raw_answer = result.get("answer", "")
    content = clean_response(raw_answer, result.get("backend", "")) or raw_answer
    backend = result.get("backend", "unknown")
    intent_name = intent.get("intent", "unknown")
    duration_ms = int((time.time() - ctx.t0) * 1000)
    raw_total_ms = result.get("total_ms")
    total_ms = duration_ms if raw_total_ms is None else raw_total_ms
    country = await resolve_ip_country(ctx.client_ip)

    _fire_side_effects(ctx, req, content, backend, intent_name, duration_ms, record_request, result, country=country)

    if ctx.fmt == "anthropic":
        response = JSONResponse(build_anthropic_response(ctx.chat_id, content, backend, ctx.request_model or model_id))
    else:
        response = JSONResponse(
            attach_memory_recall_meta(
                build_response(ctx.chat_id, content, backend, total_ms),
                ctx.memory_recall_meta,
            )
        )

    trace = get_current_trace()
    if trace is not None:
        response.headers["X-LiMa-Trace-Id"] = trace.trace_id
    return response


def _log_system_prompt(req: ChatRequest) -> None:
    sys_prompt = extract_system_prompt(req.messages)
    if not sys_prompt:
        return
    _safe_side_effect("log_sys_prompt", log_sys_prompt, sys_prompt)
