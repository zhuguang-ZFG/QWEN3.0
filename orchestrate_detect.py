"""Orchestration trigger heuristics."""

from __future__ import annotations

import re

from orchestrate_constants import (
    COMPLEXITY_THRESHOLD,
    MULTI_DOMAIN_KEYWORDS,
    MULTI_STEP_INDICATORS,
)


def needs_orchestration(query: str, intent: dict) -> bool:
    """Return True when query complexity warrants multi-model orchestration."""
    complexity = intent.get("complexity", 0.5)

    if complexity < COMPLEXITY_THRESHOLD:
        return False

    domains_hit = 0
    for _domain, keywords in MULTI_DOMAIN_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            domains_hit += 1
    if domains_hit >= 2:
        return True

    step_count = sum(1 for ind in MULTI_STEP_INDICATORS if re.search(ind, query))
    if step_count >= 2:
        return True

    if len(query) > 300 and complexity >= 0.8:
        return True

    return False
