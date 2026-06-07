"""Stage 6: OpenViking context enrichment processor.

Queries the OpenViking server for relevant resources based on the
last user message, and injects results into the system prompt.

Gated by LIMA_OPENVIKING_ENABLED=1 env var.
"""
from __future__ import annotations

import logging

from openviking_client import get_openviking_client

from . import RequestContext

_log = logging.getLogger(__name__)


def _extract_query(messages: list[dict]) -> str:
    """Extract search query from the last user message."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:500]
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part["text"][:500]
    return ""


def openviking_context_processor(ctx: RequestContext) -> RequestContext:
    """Stage 6: Enrich context with OpenViking knowledge retrieval.

    Only activates for coding scenarios when LIMA_OPENVIKING_ENABLED=1.
    Queries OpenViking with the last user message, injects top-k results
    into the system prompt as an [OpenViking Context] block.
    """
    if ctx.scenario != "coding":
        return ctx

    client = get_openviking_client()
    if client is None:
        return ctx

    query = _extract_query(ctx.messages)
    if not query:
        return ctx

    results = client.find(query, top_k=5)
    context_text = client.format_context(results, max_chars=1500)

    if not context_text:
        return ctx

    ctx.openviking_context = context_text

    # Append to system prompt as a variable block
    if ctx.system_prompt:
        ctx.system_prompt = ctx.system_prompt + "\n\n" + context_text
    else:
        ctx.system_prompt = context_text

    return ctx
