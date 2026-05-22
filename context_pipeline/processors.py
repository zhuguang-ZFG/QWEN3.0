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
    ide_keywords = [
        "claude-code", "cursor", "aider", "codex", "cline",
        "continue", "vscode", "kiro", "zed", "trae", "windsurf", "copilot",
    ]
    if any(k in ua for k in ide_keywords):
        for k in ide_keywords:
            if k in ua:
                ctx.ide = k.replace("-", "_")
                break

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
    """Stage 3: Inject relevant code context via semantic search."""
    if ctx.scenario != "coding":
        return ctx

    if os.environ.get("LIMA_CONTEXT_PREFLIGHT", "0") != "1":
        return ctx

    from code_context.index_store import InMemoryCodeIndex

    index = _get_shared_index()
    if index is None:
        return ctx

    query = ""
    for msg in reversed(ctx.messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            query = msg["content"]
            break

    if not query:
        return ctx

    matches = index.search(query, limit=3)
    if matches:
        lines = []
        for record in matches:
            symbols = ", ".join(
                f"{s.name}:{s.kind}:{s.line}" for s in record.symbols[:8]
            )
            lines.append(f"- {record.path} | {symbols}")
        ctx.code_context = "\n".join(lines)[:1200]

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


# ─── Shared state ────────────────────────────────────────────────────────────

_shared_index = None


def _get_shared_index():
    """Get the shared code index (lazy singleton)."""
    return _shared_index


def set_shared_index(index) -> None:
    """Set the shared code index (called at server startup)."""
    global _shared_index
    _shared_index = index
