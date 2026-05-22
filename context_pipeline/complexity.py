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


def assess_complexity(messages: list[dict], ide: str = "") -> ComplexityAssessment:
    """Assess request complexity to determine routing topology."""
    factors = {}
    score = 0

    user_text = _extract_user_text(messages)

    # Factor 1: Message length (token proxy)
    char_count = len(user_text)
    if char_count > 4000:
        factors["long_input"] = char_count
        score += 3
    elif char_count > 1500:
        factors["medium_input"] = char_count
        score += 1

    # Factor 2: Code presence
    code_indicators = ["```", "def ", "class ", "function ", "import ", "const "]
    code_count = sum(1 for ind in code_indicators if ind in user_text)
    if code_count >= 3:
        factors["heavy_code"] = code_count
        score += 2
    elif code_count >= 1:
        factors["has_code"] = code_count
        score += 1

    # Factor 3: Multi-file references
    file_extensions = [".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp"]
    file_refs = sum(1 for ext in file_extensions if ext in user_text)
    if file_refs >= 3:
        factors["multi_file"] = file_refs
        score += 2
    elif file_refs >= 1:
        factors["single_file"] = file_refs
        score += 1

    # Factor 4: Complexity keywords
    complex_keywords = [
        "refactor", "architecture", "migrate", "redesign",
        "concurrent", "distributed", "optimize", "performance",
    ]
    complex_count = sum(1 for k in complex_keywords if k in user_text.lower())
    if complex_count >= 2:
        factors["complex_task"] = complex_count
        score += 2
    elif complex_count >= 1:
        factors["moderate_task"] = complex_count
        score += 1

    # Factor 5: IDE presence (coding tasks are inherently more complex)
    if ide:
        score += 1
        factors["ide_present"] = ide

    # Cap score at 10
    score = min(score, 10)

    # Determine recommended parallelism and tier
    if score <= 3:
        parallelism = 1
        tier = "weak"
    elif score <= 6:
        parallelism = 1
        tier = "strong"
    else:
        parallelism = min(3, 1 + (score - 6))
        tier = "strong"

    return ComplexityAssessment(
        score=score,
        factors=factors,
        recommended_parallelism=parallelism,
        recommended_tier=tier,
    )


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
