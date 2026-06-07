"""Non-stream route execution extracted from chat_handler_dispatch (CQ-014).

Handles: intent analysis, orchestration vs v3_route dispatch,
and OpenCode direct bypass for non-streaming requests.
"""

from __future__ import annotations

import asyncio
import logging

import routing_facade
from chat_models import ChatRequest
from http_errors import BackendError
from opencode_config import OPENCODE_DIRECT_STREAM
from orchestrate import orchestrate

_log = logging.getLogger(__name__)


def _chat_handler():
    import routes.chat_handler as mod

    return mod


async def execute_non_stream_route(ctx, req: ChatRequest) -> tuple[dict, dict]:
    """Execute the non-stream route and return (result, intent).

    *ctx* is a ``ChatRunContext`` from chat_handler_dispatch.
    """
    intent = routing_facade.analyze(
        ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source
    )
    handler = _chat_handler()
    use_orchestration = (
        handler.needs_orchestration(ctx.query, intent)
        if not ctx.prefs.prefer
        else False
    )
    is_opencode = bool(
        ctx.ide_source and "opencode" in ctx.ide_source.lower()
    )
    if OPENCODE_DIRECT_STREAM and is_opencode and ctx.prefs.prefer and not use_orchestration:
        import http_caller
        from routes.opencode_direct_stream import resolve_opencode_backend

        try:
            backend = resolve_opencode_backend(ctx.prefs.prefer, require_tools=req.has_tools)
            answer = await asyncio.to_thread(
                http_caller.call_api,
                backend,
                ctx.preflight.prompt_context_messages,
                req.max_tokens or 4096,
                system_prompt=ctx.preflight.system_prompt,
                ide=ctx.ide_source,
                tools=req.tools if req.has_tools else None,
                reasoning_effort=req.reasoning_effort,
            )
            return (
                {
                    "answer": answer,
                    "backend": backend,
                    "usage": http_caller.get_last_usage(backend),
                },
                intent if isinstance(intent, dict) else {},
            )
        except BackendError as exc:
            _log.debug(
                "opencode non-stream direct path failed; using route fallback: %s",
                type(exc).__name__,
            )
    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, ctx.query)
    else:
        result = await asyncio.to_thread(
            handler.v3_route,
            ctx.query,
            ctx.preflight.request_messages,
            system_prompt=ctx.sys_prompt_preview,
            ide=ctx.ide_source,
            max_tokens=req.max_tokens or 4096,
            needs_tools=req.has_tools,
            tools=req.tools,
            client_ip=ctx.client_ip,
            user_agent=ctx.user_agent,
            model=ctx.request_model or "",
            headers=ctx.request_headers or {},
            reasoning_effort=req.reasoning_effort,
        )
    return result, intent if isinstance(intent, dict) else {}
