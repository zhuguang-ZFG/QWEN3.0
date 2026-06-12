"""Non-stream chat response closeout helpers."""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi.responses import JSONResponse

from chat_models import ChatRequest, extract_system_prompt
from response_builder import build_anthropic_response, build_response
from response_cleaner import clean_response
from routes.chat_handler_dispatch import ChatRunContext
from routes.chat_post_closeout import (
    maybe_log_distill_queue,
    persist_session_memory,
    record_capability_evidence,
    record_chat_observability,
)
from routes.chat_support import attach_memory_recall_meta, log_sys_prompt

_log = logging.getLogger(__name__)


async def finalize_success_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    result: dict,
    intent: dict,
    *,
    model_id: str,
    record_request: Callable[..., None],
) -> JSONResponse:
    raw_answer = result.get("answer", "")
    content = clean_response(raw_answer, result.get("backend", "")) or raw_answer
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    intent_name = intent.get("intent", "unknown")
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
    record_chat_observability(chat_id=ctx.chat_id, backend=backend, duration_ms=duration_ms)
    record_capability_evidence(
        request_id=ctx.chat_id,
        backend=backend,
        fallback_used=bool(result.get("fallback_used")),
        latency_ms=duration_ms,
        status="ok",
    )
    maybe_log_distill_queue(query=ctx.query, content=content, intent=intent_name, backend=backend)
    _log_system_prompt(req)

    if ctx.fmt == "anthropic":
        return JSONResponse(build_anthropic_response(ctx.chat_id, content, backend, ctx.request_model or model_id))
    return JSONResponse(
        attach_memory_recall_meta(
            build_response(ctx.chat_id, content, backend, total_ms),
            ctx.memory_recall_meta,
        )
    )


def _log_system_prompt(req: ChatRequest) -> None:
    sys_prompt = extract_system_prompt(req.messages)
    if not sys_prompt:
        return
    try:
        log_sys_prompt(sys_prompt)
    except Exception as exc:
        _log.warning("log_sys_prompt failed: %s", type(exc).__name__, exc_info=True)
