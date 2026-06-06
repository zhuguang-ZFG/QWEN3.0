"""Unified post-processing for all routing paths (stream & non-stream).

Ensures semantic equivalence between:
- routing_engine.route()  (non-stream, full post-processing)
- chat_stream.stream_response()  (OpenAI SSE, previously missing sticky/cache/integrations)
- anthropic_stream paths  (Anthropic SSE, has independent logging — see anthropic_stream_branches)
"""

from __future__ import annotations

import logging

import semantic_cache
import sticky_session
from response_cleaner import clean_response
from route_post_process import apply_post_route_integrations
from routing_engine_response import with_injection_meta
from routing_engine_types import RouteResult

_log = logging.getLogger(__name__)


def finalize_route(
    *,
    final_backend: str,
    answer: str,
    backends: list[str],
    messages: list[dict],
    messages_injected: list[dict],
    req_type: str,
    scenario: str,
    ms: int,
    sticky_key: str = "",
    cache_enabled: bool = True,
    model: str = "",
    result: RouteResult | None = None,
) -> RouteResult | None:
    """Unified post-route finalization: sticky pin, cache, integrations, meta.

    For non-stream paths, pass *result* to get it back with injection_meta.
    For stream paths, omit *result* — side-effects only (sticky + cache + integrations).
    """
    # ── 1. Sticky session pin + semantic cache ──
    if final_backend not in ("exhausted", "none"):
        if sticky_key:
            sticky_session.pin_backend(sticky_key, final_backend)
        if cache_enabled and answer:
            to_cache = clean_response(answer, final_backend) or answer
            semantic_cache.put(model or "default", messages, 0, to_cache)

    # ── 2. Post-route integrations (logging, memory, weights, observability) ──
    try:
        apply_post_route_integrations(
            final_backend=final_backend,
            answer=answer or "",
            backends=backends,
            messages_injected=messages_injected,
            messages=messages,
            req_type=req_type,
            scenario=scenario,
            ms=ms,
        )
    except Exception as exc:
        _log.warning("finalize_route: post_route_integrations failed: %s", exc)

    # ── 3. Attach injection trace meta to RouteResult ──
    if result is not None:
        return with_injection_meta(result, final_backend)

    return None
