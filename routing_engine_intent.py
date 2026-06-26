"""Intent resolution helper for routing_engine.

Wraps the optional semantic-router pre-filter and falls back to the legacy
rule-based intent analyzer.
"""

from __future__ import annotations

from config.env import semantic_router_enabled, semantic_router_threshold
from routing.semantic_router import classify as semantic_classify
from routing_intent import analyze_intent


def resolve_intent(query: str, system_prompt: str, ide_source: str) -> str:
    """Return intent, using semantic router when enabled and confident."""
    if semantic_router_enabled():
        threshold = semantic_router_threshold()
        result = semantic_classify(query, threshold=threshold)
        if result is not None:
            return result[1]
    intent_result = analyze_intent(query, system_prompt=system_prompt, ide=ide_source)
    return str(intent_result.get("intent", "chat"))
