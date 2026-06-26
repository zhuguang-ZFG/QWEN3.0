"""Intent resolution helper for routing_engine.

Wraps the optional semantic-router pre-filter and falls back to the legacy
rule-based intent analyzer.
"""

from __future__ import annotations

from config.env import semantic_router_enabled, semantic_router_threshold
from routing.semantic_router import classify as semantic_classify
from routing_engine_trace import trace_span
from routing_intent import analyze_intent


def resolve_intent(query: str, system_prompt: str, ide_source: str) -> str:
    """Return intent, using semantic router when enabled and confident."""
    with trace_span("intent") as span:
        source = "default_fallback"
        confidence = 0.5
        instructor_used = False

        if semantic_router_enabled():
            threshold = semantic_router_threshold()
            result = semantic_classify(query, threshold=threshold)
            if result is not None:
                source = "semantic_router"
                intent = result[1]
                confidence = result[2]
                if span is not None:
                    span.metadata["intent"] = intent
                    span.metadata["intent_source"] = source
                    span.metadata["intent_confidence"] = confidence
                    span.metadata["instructor_used"] = instructor_used
                return intent

        intent_result = analyze_intent(query, system_prompt=system_prompt, ide=ide_source)
        intent = str(intent_result.get("intent", "chat"))
        source = intent_result.get("source", source)
        confidence = float(intent_result.get("confidence", confidence))
        instructor_used = bool(intent_result.get("instructor_used", False))

        if span is not None:
            span.metadata["intent"] = intent
            span.metadata["intent_source"] = source
            span.metadata["intent_confidence"] = confidence
            span.metadata["instructor_used"] = instructor_used
        return intent
