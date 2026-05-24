"""Quality gate and fallback helpers extracted from server.py."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import http_caller
import smart_router
from response_builder import MODEL_ID, build_anthropic_response, build_response


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


BACKEND_TIERS = {
    "L1_free": [
        "longcat_lite",
        "longcat_chat",
        "longcat",
        "longcat_thinking",
        "longcat_omni",
        "chinamobile",
    ],
    "L2_nvidia": [
        "nvidia_qwen_coder",
        "nvidia_nemotron",
        "nvidia_phi4",
        "nvidia_llama4",
        "nvidia_llama70b",
        "nvidia_mistral",
    ],
    "L2_openrouter": [
        "or_deepseek_r1",
        "or_qwen3_coder",
        "or_llama70b",
        "or_nemotron",
        "or_qwen3_80b",
    ],
    "L3_paid": [],
}

EXACT_OUTPUT_MARKERS = (
    "return exactly",
    "respond exactly",
    "output exactly",
    "print exactly",
    "exactly:",
    "only return",
    "only output",
    "\u53ea\u8fd4\u56de",
    "\u53ea\u8f93\u51fa",
    "\u4ec5\u8fd4\u56de",
    "\u4ec5\u8f93\u51fa",
)


def get_same_tier_backends(current_backend: str) -> list:
    """Return other backends in the same tier."""
    for _tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            return [backend for backend in backends if backend != current_backend]
    return []


def get_upgrade_chain(current_backend: str) -> list:
    """Return backends from higher tiers, preserving tier order."""
    tiers = list(BACKEND_TIERS.keys())
    current_tier = None
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            current_tier = tier
            break
    if not current_tier:
        return ["longcat_chat"]
    tier_idx = tiers.index(current_tier)
    upgrade_backends = []
    for tier in tiers[tier_idx + 1:]:
        upgrade_backends.extend(BACKEND_TIERS[tier][:2])
    return upgrade_backends


def default_route(query: str, ide: str = "unknown") -> str:
    """Fallback route when router output is invalid."""
    query_len = len(query)
    if query_len < 50:
        return "longcat_lite"
    code_keywords = [
        "\u4ee3\u7801",
        "code",
        "\u51fd\u6570",
        "function",
        "bug",
        "error",
        "def ",
        "class ",
        "import ",
    ]
    if any(keyword in query.lower() for keyword in code_keywords):
        return "nvidia_qwen_coder"
    if query_len > 200:
        return "longcat"
    return "longcat_chat"


def allows_short_direct_answer(query: str, response_text: str) -> bool:
    if not query or not response_text:
        return False
    lowered = query.lower()
    if not any(marker in lowered for marker in EXACT_OUTPUT_MARKERS):
        return False
    return 1 <= len(response_text.strip()) <= 120


def _strip_direct_answer(value: str) -> str:
    return value.strip().strip("\"'`\u201c\u201d\u2018\u2019")


def expected_direct_answer(query: str) -> str:
    if not query:
        return ""
    lowered = query.lower()
    for marker in (
        "return exactly",
        "respond exactly",
        "output exactly",
        "print exactly",
        "only return",
        "only output",
    ):
        idx = lowered.rfind(marker)
        if idx < 0:
            continue
        rest = query[idx + len(marker):].strip()
        if not rest or rest[0] not in (":", "\uff1a"):
            continue
        candidate = _strip_direct_answer(rest[1:])
        if candidate and "\n" not in candidate and len(candidate) <= 120:
            return candidate
    for marker in (
        "\u53ea\u8fd4\u56de",
        "\u53ea\u8f93\u51fa",
        "\u4ec5\u8fd4\u56de",
        "\u4ec5\u8f93\u51fa",
    ):
        idx = query.rfind(marker)
        if idx < 0:
            continue
        rest = query[idx + len(marker):].strip()
        if rest.startswith((":", "\uff1a")):
            rest = rest[1:].strip()
        candidate = _strip_direct_answer(rest)
        if candidate and "\n" not in candidate and len(candidate) <= 120:
            return candidate
    return ""


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

    if len(response_text) < 30 and complexity > 0.3:
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
    return QualityGateResult(
        passed=passed,
        score=max(0.0, score),
        reasons=reasons,
        repairable=repairable,
        severity=severity,
    )


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
    request_model: str = None,
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
    if backend_name not in smart_router.BACKENDS:
        return None
    if not _backend_enabled.get(backend_name, True):
        return None
    if not smart_router.cb_allow(backend_name):
        return None
    try:
        msgs = messages if messages else [{"role": "user", "content": query}]
        result = await asyncio.wait_for(
            asyncio.to_thread(smart_router.call_api, backend_name, msgs, max_tokens),
            timeout=35.0,
        )
        if result is None or (
            isinstance(result, str)
            and (
                result.startswith("[ERR]")
                or "\u6682\u65f6\u4e0d\u53ef\u7528" in result
            )
        ):
            smart_router.cb_record(backend_name, False)
            return None
        return {"answer": result, "backend": backend_name, "total_ms": 0}
    except asyncio.TimeoutError:
        smart_router.cb_record(backend_name, False)
        return None
    except Exception as exc:
        logging.debug(
            "[TRY_BACKEND] %s: %s: %s",
            backend_name,
            type(exc).__name__,
            exc,
        )
        smart_router.cb_record(backend_name, False)
        return None
