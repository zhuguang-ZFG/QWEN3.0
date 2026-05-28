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
        from session_memory.store import save_memory, save_typed_memory

        session_id = memory_session_id or hashlib.md5((client_ip or "anon").encode()).hexdigest()[:12]

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
