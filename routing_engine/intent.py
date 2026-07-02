"""Intent resolution helper for routing_engine.

Wraps the optional semantic-router pre-filter and falls back to the legacy
rule-based intent analyzer.
"""

from __future__ import annotations

from config.env import semantic_router_enabled, semantic_router_threshold
from routing.semantic_router import classify as semantic_classify
from .trace import trace_span
from routing_intent import analyze_intent


def resolve_intent(query: str, system_prompt: str, ide_source: str, precomputed_intent: dict | None = None) -> str:
    """Return intent, using semantic router when enabled and confident.

    AUDIT-8-P2: precomputed_intent 允许上游传入已算好的 analyze_intent 结果（dict），
    避免一次请求里重复调用 analyze_intent（含可能的 instructor HTTP 调用）。
    注意：semantic_router 启用且命中时仍优先走 semantic_router（行为不变），
    precomputed_intent 只短路 analyze_intent 的回退路径。
    """
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

        # AUDIT-8-P2：上游已算好则复用，避免重复 analyze_intent（含 instructor HTTP）
        intent_result = (
            precomputed_intent
            if precomputed_intent
            else analyze_intent(query, system_prompt=system_prompt, ide=ide_source)
        )
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
