"""Post-route closeout for chat handler (CQ-014 slice 10)."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections.abc import Callable

from fastapi.responses import JSONResponse

from chat_models import ChatRequest, extract_system_prompt
from response_builder import build_anthropic_response, build_response

_log = logging.getLogger(__name__)


def persist_session_memory(
    *,
    client_ip: str,
    memory_session_id: str | None,
    query: str,
    content: str,
) -> None:
    try:
        from session_memory.compactor import compact_session, needs_compaction
        from session_memory.store import save_memory, save_typed_memory

        session_id = memory_session_id or hashlib.md5(
            (client_ip or "anon").encode(),
            usedforsecurity=False,
        ).hexdigest()[:12]

        # Save raw messages
        save_memory(session_id, "user", query[:200])
        if content:
            save_memory(session_id, "assistant", content[:200])

        # Extract and save structured observations
        observations = _extract_observations(query, content)
        for obs_type, obs_content in observations:
            try:
                save_typed_memory(session_id, obs_type, obs_content)
            except Exception as exc:
                _log.debug("save_typed_memory failed: %s, falling back to raw", type(exc).__name__)
                save_memory(session_id, obs_type, obs_content[:100])

        if needs_compaction(session_id):
            compact_session(session_id)
    except ImportError:
        _log.debug("session_memory not installed; skipping persist_session_memory")
    except Exception as exc:
        _log.warning(
            "persist_session_memory failed: %s",
            type(exc).__name__,
            exc_info=True,
        )


def _extract_observations(query: str, content: str) -> list[tuple[str, str]]:
    """Extract structured observations from a coding interaction."""
    import re
    obs: list[tuple[str, str]] = []

    combined = (query + " " + content)[:5000]

    # What tech/area was involved?
    tech_patterns = [
        (r"router|routing|backend|selector|executor|engine", "area:routing"),
        (r"tool|forward|stream|SSE|anthropic|openai", "area:tool_calling"),
        (r"memory|session|context|cache|compress", "area:context"),
        (r"CLI|headless|TUI|command|terminal", "area:cli"),
        (r"proxy|cookie|reverse|scrap", "area:reverse_proxy"),
        (r"test|E2E|smoke|validate|verify", "area:testing"),
        (r"deploy|VPS|systemd|nginx", "area:deployment"),
        (r"Kimi|SCNet|MiMo|LongCat|GPT|Mistral", "area:backend"),
    ]
    for pattern, area_tag in tech_patterns:
        if re.search(pattern, combined, re.I):
            obs.append(("observation", f"{area_tag} {query[:80]}"))

    # What was the outcome?
    if any(kw in content.lower() for kw in ["pass", "success", "works", "fixed", "通过"]):
        obs.append(("outcome", f"success: {query[:80]}"))
    elif any(kw in content.lower() for kw in ["fail", "error", "bug", "broken", "失败"]):
        obs.append(("outcome", f"issue: {query[:80]}"))

    # Extract file mentions for context linking
    files = re.findall(r"\b([\w/\\-]+\.(?:py|ts|tsx|js|go|rs))\b", combined)
    for f in files[:5]:
        obs.append(("file_mention", f"{f}: {query[:60]}"))

    # Extract error types
    errors = re.findall(
        r"\b(TypeError|ValueError|SyntaxError|ImportError|AttributeError|"
        r"KeyError|ZeroDivisionError|RuntimeError|ConnectionError)\b", combined,
    )
    for e in errors[:3]:
        obs.append(("error_seen", f"{e}: {query[:60]}"))

    return obs[:8]  # Cap at 8 observations per interaction


def record_chat_observability(*, chat_id: str, backend: str, duration_ms: int) -> None:
    try:
        from observability.correlation import record_request_correlation

        record_request_correlation(
            request_id=chat_id,
            backend=backend,
            status="success",
            latency_ms=duration_ms,
        )
    except ImportError:
        _log.debug("chat_post_closeout: optional module not available", exc_info=True)
def maybe_log_distill_queue(*, query: str, content: str, intent, backend: str) -> None:
    if os.environ.get("DISTILL_LOG", "0") != "1":
        return
    try:
        import distill_queue

        intent_payload = intent if isinstance(intent, dict) else {"intent": intent}
        distill_queue.log_to_distill_queue(query, content, intent_payload, backend)
    except Exception as exc:
        _log.debug("distill queue log skipped: %s", type(exc).__name__)


def record_capability_evidence(
    *,
    request_id: str = "",
    backend: str = "",
    fallback_used: bool = False,
    latency_ms: int = 0,
    status: str = "ok",
) -> None:
    """Record chat/IDE capability evidence. Best-effort."""
    try:
        from observability.capability_evidence import record_evidence

        record_evidence(
            loop="chat_ide",
            request_id=request_id,
            entrypoint="/v1/chat/completions",
            selected_backend=backend,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            status=status,
            evidence=["chat_post_closeout"],
        )
    except Exception as exc:
        _log.warning("capability evidence failed", exc_info=True)


async def finalize_success_response(
    ctx,
    req: ChatRequest,
    result: dict,
    intent: dict,
    *,
    model_id: str,
    record_request: Callable[..., None],
) -> JSONResponse:
    """Build the final JSON response for a successful non-stream chat request.

    *ctx* is a ``ChatRunContext`` from chat_handler_dispatch.
    Includes quality gating, session memory, observability, and distill logging.
    """
    from response_cleaner import clean_response
    from routes.chat_fallback import QualityFallbackRequest, resolve_quality_fallback
    from routes.chat_support import attach_lima_meta, attach_memory_recall_meta, log_sys_prompt

    content = result.get("answer", "")
    content = clean_response(content, result.get("backend", "")) or content
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    usage = result.get("usage")
    intent_name = intent.get("intent", "unknown")
    complexity = intent.get("complexity", 0.5)

    def _chat_handler():
        import routes.chat_handler as mod
        return mod

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
        ctx.query, backend, intent_name, duration_ms, True,
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
        attach_lima_meta(
            build_response(ctx.chat_id, content, backend, total_ms, usage=usage),
            memory_meta=ctx.memory_recall_meta,
            injection_meta=result.get("injection_meta"),
        )
    )
