"""Session memory enhancer: extracts key decisions from coding sessions.

After a coding session, analyzes the conversation to extract:
- Architecture decisions (patterns, frameworks, approaches)
- Code conventions (naming, structure, error handling)
- Backend preferences (which model worked best for which task)

Stores extracted decisions in L3 routing skills for future recall.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

_log = logging.getLogger(__name__)

_DECISION_PATTERNS = [
    (re.compile(r"(?:use|use\s+the|prefer|采用|使用)\s+(\w[\w\s]{2,30})\s+(?:for|to|pattern|方式)", re.I), "tool_choice"),
    (re.compile(r"(?:pattern|模式|方案)\s*(?:is|=|:)\s*(\w[\w\s]{2,30})", re.I), "pattern"),
    (re.compile(r"(?:convention|约定|规范)\s*(?:is|=|:)\s*(\w[\w\s]{2,30})", re.I), "convention"),
    (re.compile(r"(?:architecture|架构)\s*(?:should|must|will)\s*(\w[\w\s]{2,30})", re.I), "architecture"),
    (re.compile(r"(?:always|never|always\s+use|don't\s+use)\s+(\w[\w\s]{2,30})", re.I), "rule"),
]

_BACKEND_PATTERNS = [
    re.compile(r"(\w+)\s+(?:is\s+fast|works\s+well|performed\s+best|速度快|效果好)", re.I),
    re.compile(r"(?:use|try)\s+(\w+)\s+(?:for|because|因为)", re.I),
]


@dataclass
class ExtractedDecision:
    category: str  # "tool_choice" | "pattern" | "convention" | "architecture" | "rule" | "backend_pref"
    key: str
    confidence: float
    source: str = ""


def extract_decisions(
    messages: list[dict],
    *,
    backend: str = "",
    scenario: str = "",
) -> list[ExtractedDecision]:
    """Extract key decisions from a conversation.

    Analyzes the last few user/assistant messages for decision patterns.
    """
    decisions: list[ExtractedDecision] = []
    text = _concatenate_messages(messages)

    for pattern, category in _DECISION_PATTERNS:
        for match in pattern.finditer(text):
            key = match.group(1).strip()[:50]
            if len(key) > 3:
                decisions.append(ExtractedDecision(
                    category=category,
                    key=key,
                    confidence=0.6,
                    source="pattern_match",
                ))

    for pattern in _BACKEND_PATTERNS:
        for match in pattern.finditer(text):
            backend_name = match.group(1).strip()
            if len(backend_name) > 2:
                decisions.append(ExtractedDecision(
                    category="backend_pref",
                    key=backend_name,
                    confidence=0.7,
                    source="backend_mention",
                ))

    seen = set()
    unique: list[ExtractedDecision] = []
    for d in decisions:
        key = f"{d.category}:{d.key.lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(d)

    if backend and scenario:
        unique.append(ExtractedDecision(
            category="routing_preference",
            key=f"{scenario}:{backend}",
            confidence=0.5,
            source="session_outcome",
        ))

    return unique[:10]


def store_decisions(decisions: list[ExtractedDecision]) -> int:
    """Store extracted decisions into L3 routing skills.

    Returns the number of decisions stored.
    """
    stored = 0
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        for d in decisions:
            skill_key = f"decision:{d.category}:{d.key[:30]}"
            hmem.store_skill(skill_key, {
                "category": d.category,
                "key": d.key,
                "confidence": d.confidence,
                "source": d.source,
                "stored_at": time.time(),
            })
            stored += 1
    except Exception as exc:
        _log.debug("store_decisions failed: %s", exc)

    return stored


def process_session_outcome(
    messages: list[dict],
    *,
    backend: str = "",
    scenario: str = "",
    success: bool = True,
) -> int:
    """Full pipeline: extract decisions from session, store in L3.

    Call this at the end of a coding session.
    """
    if not success:
        return 0

    decisions = extract_decisions(messages, backend=backend, scenario=scenario)
    if not decisions:
        return 0

    stored = store_decisions(decisions)
    _log.info("Session memory: extracted %d decisions, stored %d", len(decisions), stored)
    return stored


def recall_relevant_decisions(query: str, limit: int = 3) -> list[dict]:
    """Recall relevant decisions from L3 for a new query."""
    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        results = hmem.L3.search("decision:")
        relevant = []
        query_lower = query.lower()
        for key, value in results:
            if isinstance(value, dict):
                decision_key = value.get("key", "").lower()
                if any(term in decision_key for term in query_lower.split() if len(term) > 3):
                    relevant.append(value)
        return relevant[:limit]
    except Exception:
        return []


def _concatenate_messages(messages: list[dict]) -> str:
    parts = []
    for msg in messages[-6:]:
        if isinstance(msg, dict):
            parts.append(str(msg.get("content", ""))[:500])
    return " ".join(parts)
