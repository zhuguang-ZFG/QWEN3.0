"""Request complexity assessor — AgentConductor-inspired dynamic topology.

Determines request complexity to drive dynamic ensemble decisions:
- Simple (score 1-3): 1 backend, direct response
- Medium (score 4-6): 1 strong backend, no parallelism
- Complex (score 7-10): 2-3 backends parallel race (ensemble)

Complexity factors:
- Message length (token proxy)
- Code presence and nesting depth
- Multi-file references
- System prompt complexity
- Historical failure rate for similar requests
"""

from dataclasses import dataclass


@dataclass
class ComplexityAssessment:
    """Result of request complexity analysis."""

    score: int  # 1-10
    factors: dict
    recommended_parallelism: int  # 1, 2, or 3
    recommended_tier: str  # "weak", "medium", "strong"


_CODE_INDICATORS = ["```", "def ", "class ", "function ", "import ", "const "]
_FILE_EXTENSIONS = [".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp"]
_COMPLEX_KEYWORDS = [
    "refactor", "architecture", "migrate", "redesign",
    "concurrent", "distributed", "optimize", "performance",
]

# (signal_list, high_threshold, low_threshold, high_label, low_label, high_score, low_score)
_FACTORS = [
    ("char_count", None, 4000, 1500, "long_input", "medium_input", 3, 1),
    ("code", _CODE_INDICATORS, 3, 1, "heavy_code", "has_code", 2, 1),
    ("files", _FILE_EXTENSIONS, 3, 1, "multi_file", "single_file", 2, 1),
    ("keywords", _COMPLEX_KEYWORDS, 2, 1, "complex_task", "moderate_task", 2, 1),
]


def _score_factor(user_text: str, spec: tuple) -> tuple[str, str | None, int]:
    """Score one complexity factor. Returns (label, value, score_delta)."""
    kind, signals, hi, lo, hi_label, lo_label, hi_s, lo_s = spec
    if kind == "char_count":
        n = len(user_text)
    else:
        n = sum(1 for ind in signals if ind in user_text)
    if n >= hi:
        return hi_label, str(n), hi_s
    if n >= lo:
        return lo_label, str(n), lo_s
    return "", None, 0


def _resolve_topology(score: int) -> tuple[int, str]:
    """Determine parallelism and tier from score."""
    if score <= 3:
        return 1, "weak"
    if score <= 6:
        return 1, "strong"
    return min(3, 1 + (score - 6)), "strong"


def assess_complexity(messages: list[dict], ide: str = "") -> ComplexityAssessment:
    """Assess request complexity to determine routing topology."""
    user_text = _extract_user_text(messages)
    factors = {}
    score = 0
    for spec in _FACTORS:
        label, value, delta = _score_factor(user_text, spec)
        if label:
            factors[label] = value
            score += delta
    if ide:
        score += 1
        factors["ide_present"] = ide
    score = min(score, 10)
    parallelism, tier = _resolve_topology(score)
    return ComplexityAssessment(score=score, factors=factors,
                                recommended_parallelism=parallelism, recommended_tier=tier)


def _extract_user_text(messages: list[dict]) -> str:
    """Extract all user text from messages."""
    parts = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
    return " ".join(parts)


def dynamic_ensemble_decision(
    messages: list[dict],
    ide: str = "",
    available_backends: list[str] | None = None,
) -> dict:
    """AgentConductor-style dynamic topology decision.

    Returns routing topology recommendation:
    - parallelism: how many backends to use
    - tier: minimum backend quality tier
    - strategy: "direct" | "single_strong" | "ensemble_race"
    """
    assessment = assess_complexity(messages, ide)

    if assessment.recommended_parallelism == 1 and assessment.recommended_tier == "weak":
        strategy = "direct"
    elif assessment.recommended_parallelism == 1:
        strategy = "single_strong"
    else:
        strategy = "ensemble_race"

    return {
        "strategy": strategy,
        "parallelism": assessment.recommended_parallelism,
        "tier": assessment.recommended_tier,
        "complexity_score": assessment.score,
        "factors": assessment.factors,
    }
