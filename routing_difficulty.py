"""Task difficulty estimation for tiered model routing.

Estimates coding task complexity on a 0-100 scale to route:
- Simple tasks (0-30) → free/budget models
- Medium tasks (30-70) → mid-tier models
- Hard tasks (70-100) → premium models
"""

from __future__ import annotations


def estimate_difficulty(
    query: str,
    messages: list[dict],
    *,
    scenario: str = "",
) -> int:
    """Return difficulty score 0-100 based on task signals.

    0 = trivial (single-line fix, simple question)
    50 = moderate (feature implementation, bug fix)
    100 = very hard (architecture design, multi-system integration)

    Args:
        query: User query string (may be empty if from messages).
        messages: OpenAI-format messages list.
        scenario: Task scenario (e.g. 'coding', 'chat').

    Returns:
        Integer difficulty score 0-100.
    """
    score = 0

    # Extract last user text
    text = _extract_last_user_text(query, messages)

    # ── Complexity signals (each adds weighted points) ──

    # Multi-file / large scope
    if any(s in text for s in ("refactor", "migrate", "restructure", "redesign")):
        score += 25
    if any(s in text for s in ("entire project", "across all", "every file")):
        score += 20
    if any(s in text for s in ("multiple files", "several files", "many files")):
        score += 15

    # Architecture / design
    if any(s in text for s in ("architecture", "design pattern", "system design")):
        score += 20
    if any(s in text for s in ("database schema", "data model", "API design")):
        score += 15

    # Algorithm / complexity
    if any(s in text for s in ("algorithm", "optimize", "performance", "concurrent")):
        score += 15
    if any(s in text for s in ("O(n)", "time complexity", "space complexity")):
        score += 10

    # Integration / external systems
    if any(s in text for s in ("integrate", "connect to", "API integration", "webhook")):
        score += 10
    if any(s in text for s in ("docker", "kubernetes", "deploy", "CI/CD")):
        score += 10

    # Code length signals
    code_block_count = text.count("```")
    if code_block_count >= 6:
        score += 15  # Multiple code blocks = complex
    elif code_block_count >= 2:
        score += 5

    # Message count (multi-turn = more context)
    user_msg_count = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
    if user_msg_count >= 5:
        score += 10  # Long conversation suggests complexity
    elif user_msg_count >= 3:
        score += 5

    # ── Simplicity signals (reduces score) ──

    if any(s in text for s in ("simple", "quick", "one line", "just")):
        score -= 15
    # Very short queries get a penalty, but not when complexity signals exist
    if len(text.split()) < 10 and score < 10:
        score -= 20

    return max(0, min(100, score))


def _extract_last_user_text(query: str, messages: list[dict]) -> str:
    """Get last user message content as lowercase string."""
    text = query
    if messages:
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                elif isinstance(content, str):
                    text = content
                break
    return text.lower()
