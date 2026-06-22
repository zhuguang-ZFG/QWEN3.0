"""Post-route closeout for chat handler (CQ-014 slice 10)."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import sys
import time

_log = logging.getLogger(__name__)

_DISTILL_QUEUE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "distill_queue", "pending")
_DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"


def _quick_score(query: str, answer: str) -> float:
    """Heuristic quality score for distill queue entries."""
    if not answer:
        return 0.0

    length = len(answer)
    if 100 <= length <= 2000:
        len_score = 1.0
    elif length < 50:
        len_score = 0.0
    elif length < 100:
        len_score = (length - 50) / 50
    else:
        len_score = max(0.7, 1.0 - (length - 2000) / 5000)

    fmt_score = 0.0
    if "```" in answer and answer.count("```") % 2 == 0:
        fmt_score += 0.4
    if any(char.isdigit() for char in answer):
        fmt_score += 0.3
    if any(marker in answer for marker in ["1.", "2.", "- ", "* ", "步骤"]):
        fmt_score += 0.3

    comp_score = 1.0
    if any(marker in answer for marker in ["抱歉", "无法", "不确定", "我不能", "暂时不可用"]):
        comp_score = 0.3

    query_words = set(query.lower().replace("?", "").replace("？", "").split())
    answer_lower = answer.lower()
    overlap = sum(1 for word in query_words if word and word in answer_lower)
    overlap_score = min(1.0, overlap / max(1, len(query_words)))

    return 0.3 * len_score + 0.25 * fmt_score + 0.25 * comp_score + 0.2 * overlap_score


def _log_to_distill_queue(query: str, answer: str, intent: dict, backend: str) -> None:
    """Write a distill-queue entry for later retraining/annotation."""
    if os.environ.get("DISTILL_LOG", "0") != "1":
        return
    if backend == "local":
        return
    if not answer or "暂时不可用" in answer:
        return

    try:
        os.makedirs(_DISTILL_QUEUE_DIR, exist_ok=True)
        score = _quick_score(query, answer)
        entry = {
            "query": query,
            "answer": answer,
            "intent": intent.get("intent", "unknown"),
            "complexity": intent.get("complexity", 0.5),
            "source_backend": backend,
            "quality_score": score,
            "routing_correct": score >= 0.7,
            "logged_at": datetime.datetime.now().isoformat(),
        }
        qhash = hashlib.md5(query.encode()).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(_DISTILL_QUEUE_DIR, f"{ts}_{qhash}.json")
        with open(fname, "w", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=2)
        if _DEBUG:
            print(f"[DISTILL] logged: {query[:30]}... -> {backend}", file=sys.stderr)
    except Exception as exc:
        if _DEBUG:
            print(f"[DISTILL] log failed: {exc}", file=sys.stderr)


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
                _log.warning("save_typed_memory failed: %s, falling back to raw", exc)
                save_memory(session_id, obs_type, obs_content[:100])

        if needs_compaction(session_id):
            compact_session(session_id)
    except ImportError as exc:
        _log.warning("session_memory not installed; skipping persist_session_memory: %s", exc)
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
        r"KeyError|ZeroDivisionError|RuntimeError|ConnectionError)\b",
        combined,
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
    except ImportError as exc:
        _log.warning("observability.correlation not installed; request correlation not recorded: %s", exc)


def maybe_log_distill_queue(*, query: str, content: str, intent, backend: str) -> None:
    if os.environ.get("DISTILL_LOG", "0") != "1":
        return
    try:
        intent_payload = intent if isinstance(intent, dict) else {"intent": intent}
        _log_to_distill_queue(query, content, intent_payload, backend)
    except Exception as exc:
        _log.warning("distill queue log skipped: %s", exc, exc_info=True)


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
