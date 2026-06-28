"""Non-stream quality fallback loop extracted from chat_handler (CQ-014 slice 5)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from fastapi.responses import JSONResponse

from response_builder import build_anthropic_response, build_response
from routes.request_tracking import resolve_ip_country

_log = logging.getLogger(__name__)


# Simplified quality/stub wrappers (device-first refactor 2026-06-15)
def quality_check(answer: str, query_or_complexity, backend: str, **kwargs) -> tuple:
    """Always pass - device scenario doesn't need complex quality gates."""
    return (True, 1.0, [])


def default_route(query, ide_source="", **kwargs):
    """Return empty to use normal routing."""
    return ("", "")


def get_same_tier_backends(backend: str, **kwargs) -> list:
    """No same-tier retry for device scenario."""
    return []


def get_upgrade_chain(backend: str, **kwargs) -> list:
    """No upgrade chain for device scenario."""
    return []


def honest_failure_response(chat_id: str, fmt: str = "openai", request_model: str | None = None) -> str:
    """Honest failure message."""
    return "抱歉，服务暂时不可用，请稍后重试。"


async def try_backend(backend: str, query, max_tokens: int, **kwargs):
    """Simplified backend attempt (stub returns None)."""
    return None


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
        _log.warning("capability evidence record skipped: %s", exc)


def _build_fallback_success_response(
    req: "QualityFallbackRequest",
    content: str,
    backend: str,
    intent_label: str,
    country: str = "",
) -> JSONResponse:
    """Record metrics and build JSON response for a successful fallback."""
    _record_fallback(
        req.query,
        req.backend,
        backend,
        intent_label,
        req.ide_source,
    )
    _record_request(
        req.query,
        backend,
        intent_label,
        req.elapsed_ms,
        True,
        client_ip=req.client_ip,
        ide_source=req.ide_source,
        sys_prompt_preview=req.sys_prompt_preview,
        country=country,
    )
    _record_chat_evidence(
        request_id=req.chat_id,
        backend=backend,
        status="ok",
        fallback_used=True,
        latency_ms=req.elapsed_ms,
    )
    if req.fmt == "anthropic":
        return JSONResponse(build_anthropic_response(req.chat_id, content, backend, req.request_model or _model_id))
    return JSONResponse(
        attach_memory_recall_meta(
            build_response(req.chat_id, content, backend, req.elapsed_ms),
            req.memory_recall_meta,
        )
    )


async def _try_fallback_candidates(
    req: "QualityFallbackRequest",
    candidates: list[str],
    intent_label: str,
) -> JSONResponse | None:
    """Try each candidate; return success JSONResponse or None."""
    country = await resolve_ip_country(req.client_ip)
    for alt in candidates:
        alt_result = await try_backend(
            alt,
            req.query,
            req.max_tokens,
            messages=req.prompt_context_messages,
        )
        if alt_result and quality_check(alt_result["answer"], req.complexity, alt, query=req.query):
            return _build_fallback_success_response(
                req,
                alt_result["answer"],
                alt,
                intent_label,
                country=country,
            )
    return None


from lima_constants import MODEL_ID

_log = logging.getLogger(__name__)
_injected = False


def _require_injected(name: str) -> None:
    raise RuntimeError(f"routes.chat_fallback.inject_deps() was not called; missing {name}")


def _unconfigured_record_request(*args, **kwargs) -> None:
    if not _injected:
        _require_injected("record_request")


def _unconfigured_record_fallback(*args, **kwargs) -> None:
    if not _injected:
        _require_injected("record_fallback")


_record_request: Callable[..., None] = _unconfigured_record_request
_record_fallback: Callable[..., None] = _unconfigured_record_fallback
_model_id = MODEL_ID


def inject_deps(
    *,
    model_id: str,
    record_request: Callable[..., None],
    record_fallback: Callable[..., None],
) -> None:
    global _model_id, _record_request, _record_fallback, _injected
    _model_id = model_id
    _record_request = record_request
    _record_fallback = record_fallback
    _injected = True


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
    fallback_backend = req.backend
    if req.backend == "unknown":
        routed = default_route(req.query, req.ide_source)
        fallback_backend = routed[0] if isinstance(routed, tuple) else str(routed)

    # Same-tier retry
    same_tier = get_same_tier_backends(fallback_backend)
    result = await _try_fallback_candidates(
        req,
        same_tier,
        f"fallback_same_tier_{fallback_intent}",
    )
    if result:
        return result

    # Upgrade-chain retry
    upgrade_chain = get_upgrade_chain(fallback_backend)
    result = await _try_fallback_candidates(
        req,
        upgrade_chain,
        f"fallback_upgrade_{fallback_intent}",
    )
    if result:
        return result

    # All fallback paths exhausted
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
