"""LLM-powered synthesis of search results into coherent answers.

Uses LiMa's backend routing to synthesize multiple search hits into
a single coherent, source-attributed answer.
"""

from __future__ import annotations

import logging
import os
from research.source_adapters import SearchHit

_log = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 4000


def synthesize_results(query: str, hits: list[SearchHit]) -> str:
    """Synthesize search hits into a coherent answer using LiMa's routing.

    Falls back to simple concatenation if LLM synthesis fails.
    """
    if not hits:
        return f"No results found for: {query}"

    context = _build_context(hits)

    try:
        answer = _call_llm(query, context)
        if answer and len(answer) > 50:
            return answer
    except Exception as exc:
        _log.debug("LLM synthesis failed: %s", exc)

    return _fallback_synthesis(query, hits)


def _build_context(hits: list[SearchHit]) -> str:
    parts = []
    total = 0
    for i, hit in enumerate(hits[:10], 1):
        entry = f"[{i}] {hit.title}\n{hit.url}\n{hit.snippet}"
        if total + len(entry) > _MAX_CONTEXT_CHARS:
            break
        parts.append(entry)
        total += len(entry)
    return "\n\n".join(parts)


def _call_llm(query: str, context: str) -> str:
    """Call LiMa's routing engine for synthesis."""
    import httpx

    router_url = os.environ.get("LIMA_ROUTER_URL", "http://127.0.0.1:8080")
    prompt = (
        f"Based on the following search results, provide a concise answer to: {query}\n\n"
        f"Search results:\n{context}\n\n"
        f"Answer with specific facts and cite source numbers [1], [2], etc."
    )

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            f"{router_url}/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.3,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    return ""


def _fallback_synthesis(query: str, hits: list[SearchHit]) -> str:
    """Simple concatenation fallback when LLM is unavailable."""
    parts = [f"Research results for: {query}\n"]
    for i, hit in enumerate(hits[:5], 1):
        parts.append(f"{i}. **{hit.title}**")
        parts.append(f"   {hit.url}")
        parts.append(f"   {hit.snippet[:200]}")
        parts.append("")
    return "\n".join(parts)
