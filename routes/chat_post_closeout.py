"""Post-route closeout for chat handler (CQ-014 slice 10)."""

from __future__ import annotations

import hashlib
import logging
import os

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
        from session_memory.store import save_memory

        session_id = memory_session_id or hashlib.md5((client_ip or "anon").encode()).hexdigest()[:12]
        save_memory(session_id, "user", query[:100])
        if content:
            save_memory(session_id, "assistant", content[:100])
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
        pass


def maybe_log_distill_queue(*, query: str, content: str, intent, backend: str) -> None:
    if os.environ.get("DISTILL_LOG", "0") != "1":
        return
    try:
        import smart_router

        intent_payload = intent if isinstance(intent, dict) else {"intent": intent}
        smart_router._log_to_distill_queue(query, content, intent_payload, backend)
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
    except Exception:
        _log.warning("capability evidence failed", exc_info=True)
