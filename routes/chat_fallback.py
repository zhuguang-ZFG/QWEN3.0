"""Non-stream quality fallback loop extracted from chat_handler (CQ-014 slice 5)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from fastapi.responses import JSONResponse

from response_builder import build_anthropic_response, build_response

_log = logging.getLogger(__name__)

from routes.quality_gate import (
    default_route,
    get_same_tier_backends,
    get_upgrade_chain,
    honest_failure_response,
    quality_check,
    try_backend,
)

from routes.chat_support import attach_memory_recall_meta


def _record_chat_evidence(*, request_id: str, backend: str, status: str, fallback_used: bool, latency_ms: int) -> None:
    try:
        from observability.capability_evidence import record_evidence_safe

        record_evidence_safe(
            loop="chat_ide",
            request_id=request_id,
            entrypoint="/v1/chat/completions",
            selected_backend=backend,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            status=status,
            evidence=["chat_fallback"],
        )
    except Exception as exc:
        _log.debug("capability evidence record skipped: %s", type(exc).__name__)

_record_request: Callable[..., None] = lambda *a, **kw: None
_record_fallback: Callable[..., None] = lambda *a, **kw: None
_model_id = "lima-1.3"


def inject_deps(
    *,
    model_id: str,
    record_request: Callable[..., None],
    record_fallback: Callable[..., None],
) -> None:
    global _model_id, _record_request, _record_fallback
    _model_id = model_id
    _record_request = record_request
    _record_fallback = record_fallback


@dataclass
class QualityFallbackRequest:
    chat_id: str
    query: str
    content: str
    backend: str
    complexity: float
    intent_name: str
    fmt: str
    request_model: str | None
    max_tokens: int
    ide_source: str
    client_ip: str
    sys_prompt_preview: str
    prompt_context_messages: list
    memory_recall_meta: dict
    elapsed_ms: int


async def resolve_quality_fallback(req: QualityFallbackRequest) -> JSONResponse:
    """Run same-tier and upgrade-chain fallback; return success or honest failure."""
    fallback_intent = req.intent_name if req.intent_name != "unknown" else "unknown"
    fallback_backend = (
        default_route(req.query, req.ide_source)
        if req.backend == "unknown"
        else req.backend
    )

    same_tier = get_same_tier_backends(fallback_backend)
    for alt in same_tier:
        alt_result = await try_backend(
            alt,
            req.query,
            req.max_tokens,
            messages=req.prompt_context_messages,
        )
        if alt_result and quality_check(
            alt_result["answer"], req.complexity, alt, query=req.query
        ):
            content = alt_result["answer"]
            backend = alt
            _record_fallback(
                req.query,
                fallback_backend,
                alt,
                f"fallback_same_tier_{fallback_intent}",
                req.ide_source,
            )
            _record_request(
                req.query,
                backend,
                f"fallback_same_tier_{fallback_intent}",
                req.elapsed_ms,
                True,
                client_ip=req.client_ip,
                ide_source=req.ide_source,
                sys_prompt_preview=req.sys_prompt_preview,
            )
            if req.fmt == "anthropic":
                _record_chat_evidence(
                    request_id=req.chat_id,
                    backend=backend,
                    status="ok",
                    fallback_used=True,
                    latency_ms=req.elapsed_ms,
                )
                return JSONResponse(
                    build_anthropic_response(
                        req.chat_id, content, backend, req.request_model or _model_id
                    )
                )
            _record_chat_evidence(
                request_id=req.chat_id,
                backend=backend,
                status="ok",
                fallback_used=True,
                latency_ms=req.elapsed_ms,
            )
            return JSONResponse(
                attach_memory_recall_meta(
                    build_response(req.chat_id, content, backend, req.elapsed_ms),
                    req.memory_recall_meta,
                )
            )

    upgrade_chain = get_upgrade_chain(fallback_backend)
    for upgraded in upgrade_chain:
        up_result = await try_backend(
            upgraded,
            req.query,
            req.max_tokens,
            messages=req.prompt_context_messages,
        )
        if up_result and quality_check(
            up_result["answer"], req.complexity, upgraded, query=req.query
        ):
            content = up_result["answer"]
            backend = upgraded
            _record_fallback(
                req.query,
                fallback_backend,
                upgraded,
                f"fallback_upgrade_{fallback_intent}",
                req.ide_source,
            )
            _record_request(
                req.query,
                backend,
                f"fallback_upgrade_{fallback_intent}",
                req.elapsed_ms,
                True,
                client_ip=req.client_ip,
                ide_source=req.ide_source,
                sys_prompt_preview=req.sys_prompt_preview,
            )
            if req.fmt == "anthropic":
                _record_chat_evidence(
                    request_id=req.chat_id,
                    backend=backend,
                    status="ok",
                    fallback_used=True,
                    latency_ms=req.elapsed_ms,
                )
                return JSONResponse(
                    build_anthropic_response(
                        req.chat_id, content, backend, req.request_model or _model_id
                    )
                )
            _record_chat_evidence(
                request_id=req.chat_id,
                backend=backend,
                status="ok",
                fallback_used=True,
                latency_ms=req.elapsed_ms,
            )
            return JSONResponse(
                attach_memory_recall_meta(
                    build_response(req.chat_id, content, backend, req.elapsed_ms),
                    req.memory_recall_meta,
                )
            )

    _record_request(
        req.query,
        "fallback_exhausted",
        f"fallback_exhausted_{fallback_intent}",
        req.elapsed_ms,
        False,
        client_ip=req.client_ip,
        ide_source=req.ide_source,
        sys_prompt_preview=req.sys_prompt_preview,
    )
    _record_chat_evidence(
        request_id=req.chat_id,
        backend="fallback_exhausted",
        status="failed",
        fallback_used=True,
        latency_ms=req.elapsed_ms,
    )
    return JSONResponse(honest_failure_response(req.chat_id, req.fmt, req.request_model))
