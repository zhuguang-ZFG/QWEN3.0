"""Individual processors for the context pipeline.

Each processor is a function: (RequestContext) -> RequestContext
Processors are stateless transformations applied in order.
"""

from __future__ import annotations

import os

from . import RequestContext


def ide_detection_processor(ctx: RequestContext) -> RequestContext:
    """Stage 1: Detect IDE from headers and message content."""
    import router_v3

    ua = ctx.headers.get("user-agent", "").lower()
    ide_keywords = ["opencode", "opencode-ai"]
    if any(k in ua for k in ide_keywords):
        ctx.ide = "OpenCode"

    if not ctx.ide:
        for msg in ctx.messages:
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if isinstance(content, str):
                detected = router_v3.detect_ide_from_system_prompt(content)
                if detected:
                    ctx.ide = detected
                    break

    return ctx


def scenario_classification_processor(ctx: RequestContext) -> RequestContext:
    """Stage 2: Classify request scenario (coding/chat/vision)."""
    if ctx.ide:
        ctx.scenario = "coding"
    else:
        ctx.scenario = "chat"

    for msg in ctx.messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    ctx.scenario = "vision"
                    break

    return ctx


def code_context_processor(ctx: RequestContext) -> RequestContext:
    """Stage 3: Populate code_context from the unified retrieval injector.

    Uses context_pipeline.retrieval_injection.build_retrieval_text() so the
    default pipeline lab path does not maintain a separate index search lane.
    """
    if ctx.scenario != "coding":
        return ctx

    if os.environ.get("LIMA_CONTEXT_PREFLIGHT", "0") != "1":
        return ctx

    from context_pipeline.retrieval_injection import build_retrieval_text

    text = build_retrieval_text(ctx.messages)
    if text:
        ctx.code_context = text[:1200]

    return ctx


def prompt_composition_processor(ctx: RequestContext) -> RequestContext:
    """Stage 4: Compose structured system prompt from vibe-coding layers."""
    from prompt_engineering.layers import compose_system_prompt

    ctx.system_prompt = compose_system_prompt(
        ide=ctx.ide,
        scenario=ctx.scenario,
        code_context=ctx.code_context,
    )
    return ctx


def cache_optimization_processor(ctx: RequestContext) -> RequestContext:
    """Stage 5: Optimize for model prefix caching.

    Stable content (role + skill + quality gate) stays at the front.
    Variable content (code context) goes at the end.
    This maximizes prefix cache hit rate across requests.
    """
    if not ctx.system_prompt:
        return ctx

    parts = ctx.system_prompt.split("\n\n")
    stable_parts = []
    variable_parts = []

    for part in parts:
        if part.startswith("[上下文]"):
            variable_parts.append(part)
        else:
            stable_parts.append(part)

    ctx.system_prompt = "\n\n".join(stable_parts + variable_parts)
    return ctx

