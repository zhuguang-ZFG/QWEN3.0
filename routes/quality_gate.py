"""Quality gate and fallback helpers extracted from server.py."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import http_caller
import backends
import router_circuit_breaker
from response_builder import MODEL_ID, build_anthropic_response, build_response
from routes.quality_gate_direct import (
    EXACT_OUTPUT_MARKERS,
    allows_short_direct_answer,
    expected_direct_answer,
)
from routes.quality_gate_tiers import (
    BACKEND_TIERS,
    default_route,
    get_same_tier_backends,
    get_upgrade_chain,
)

_log = logging.getLogger(__name__)


@dataclass
class QualityGateResult:
    """Typed quality gate result for structured pass/fail decisions."""

    passed: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    repairable: bool = False
    severity: str = "info"

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": round(self.score, 2),
            "reasons": self.reasons,
            "repairable": self.repairable,
            "severity": self.severity,
        }


_backend_enabled: dict = {}


def inject_state(backend_enabled: dict) -> None:
    """Called once from server.py to wire in shared mutable state."""
    global _backend_enabled
    _backend_enabled = backend_enabled


def quality_check(
    response_text: str,
    complexity: float,
    backend: str,
    query: str = "",
) -> bool:
    """Check response quality. False means the caller should retry/fallback."""
    return quality_check_typed(response_text, complexity, backend, query=query).passed


def quality_check_typed(
    response_text: str,
    complexity: float,
    backend: str,
    query: str = "",
) -> QualityGateResult:
    """Typed quality check returning structured result with reasons."""
    if not response_text:
        return QualityGateResult(False, 0.0, ["empty response"], severity="error")
    if response_text.startswith("[ERR]"):
        return QualityGateResult(False, 0.0, ["error prefix"], severity="error")
    if http_caller._is_backend_error(response_text):
        return QualityGateResult(False, 0.0, ["backend error message"], severity="error")

    expected = expected_direct_answer(query)
    if expected and response_text.strip() != expected:
        return QualityGateResult(
            False,
            0.3,
            [f"expected exact '{expected}', got different"],
            severity="error",
        )

    reasons: list[str] = []
    score = 1.0

    # Short response penalty — but only for genuinely complex queries.
    # Trivial queries (short prompts, simple requests) naturally produce
    # short responses; penalizing them causes false fallback cascades.
    query_is_trivial = len(query) < 50 and not any(
        kw in query.lower()
        for kw in ("explain", "write", "implement", "debug", "analyze", "compare", "difference", "how to", "what is")
    )
    if len(response_text) < 30 and complexity > 0.3 and not query_is_trivial:
        if not allows_short_direct_answer(query, response_text):
            reasons.append("too short for complexity")
            score -= 0.4

    uncertain_phrases = [
        "I cannot",
        "I can't",
        "I am unable",
        "I won't",
        "cannot help",
        "\u6211\u65e0\u6cd5",
        "\u62b1\u6b49\uff0c\u6211\u4e0d\u80fd",
    ]
    if any(phrase in response_text for phrase in uncertain_phrases):
        if not _allows_safety_refusal(query):
            reasons.append("contains refusal")
            score -= 0.5

    if not response_text.strip().endswith(
        (".", "\u3002", "!", "\uff01", "?", "\uff1f", "```", "\n")
    ):
        if len(response_text) > 100:
            reasons.append("possibly truncated")
            score -= 0.2

    passed = score >= 0.5 and not reasons
    severity = "info" if passed else ("warning" if score >= 0.3 else "error")
    repairable = score >= 0.3 and any(
        reason.startswith("too short") or reason == "possibly truncated"
        for reason in reasons
    )
    result = QualityGateResult(
        passed=passed, score=max(0.0, score), reasons=reasons,
        repairable=repairable, severity=severity,
    )
    try:
        from observability.metrics import record as _obs_record
        from observability.events import quality_result_event
        _obs_record(quality_result_event("", backend, result.score, result.passed))
    except ImportError:
        _log.debug("observability metrics unavailable for quality_result_event")
    return result


def _allows_safety_refusal(query: str) -> bool:
    """Return True when a refusal is likely the correct answer."""
    lowered = (query or "").lower()
    safety_terms = (
        "hack into",
        "bank account",
        "steal",
        "phishing",
        "malware",
        "ransomware",
        "credential",
        "password",
        "exploit",
        "bypass authentication",
    )
    return any(term in lowered for term in safety_terms)


def honest_failure_response(
    chat_id: str,
    fmt: str = "openai",
    request_model: str | None = None,
) -> dict:
    """Build an honest response when all backends fail."""
    content = (
        "\u5f53\u524d\u6240\u6709\u670d\u52a1\u6682\u65f6\u4e0d\u53ef"
        "\u7528\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002\u5982\u679c"
        "\u95ee\u9898\u6301\u7eed\uff0c\u8bf7\u8054\u7cfb\u7ba1\u7406"
        "\u5458\u3002"
    )
    if fmt == "anthropic":
        return build_anthropic_response(
            chat_id,
            content,
            "fallback_exhausted",
            request_model or MODEL_ID,
        )
    return build_response(chat_id, content, "fallback_exhausted", 0)


async def try_backend(
    backend_name: str,
    query: str,
    max_tokens: int = 1024,
    *,
    messages: list[dict] | None = None,
) -> dict | None:
    """Try one backend and return a smart_router.route-compatible dict."""
    if backend_name not in backends.BACKENDS:
        return None
    if not _backend_enabled.get(backend_name, True):
        return None
    if not router_circuit_breaker.cb_allow(backend_name):
        return None
    try:
        msgs = messages if messages else [{"role": "user", "content": query}]
        result = await asyncio.wait_for(
            asyncio.to_thread(http_caller.call_api, backend_name, msgs, max_tokens),
            timeout=35.0,
        )
        if result is None or (
            isinstance(result, str)
            and (
                result.startswith("[ERR]")
                or "\u6682\u65f6\u4e0d\u53ef\u7528" in result
            )
        ):
            router_circuit_breaker.cb_record(backend_name, False)
            return None
        return {"answer": result, "backend": backend_name, "total_ms": 0}
    except asyncio.TimeoutError:
        router_circuit_breaker.cb_record(backend_name, False)
        return None
    except Exception as exc:
        _log.debug(
            "[TRY_BACKEND] %s: %s: %s",
            backend_name,
            type(exc).__name__,
            exc,
        )
        router_circuit_breaker.cb_record(backend_name, False)
        return None


__all__ = [
    "BACKEND_TIERS",
    "EXACT_OUTPUT_MARKERS",
    "QualityGateResult",
    "allows_short_direct_answer",
    "expected_direct_answer",
    "default_route",
    "get_same_tier_backends",
    "get_upgrade_chain",
    "honest_failure_response",
    "inject_state",
    "quality_check",
    "quality_check_typed",
    "try_backend",
]
