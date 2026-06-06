"""Response helpers for routing_engine."""

from __future__ import annotations

from response_builder import build_anthropic_response, build_response, make_chat_id
from routing_engine_types import RouteResult


def respond(result: RouteResult, fmt: str = "openai", model: str = "lima-1.3") -> dict:
    chat_id = make_chat_id()
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, result.answer, result.backend, model)
    resp = build_response(chat_id, result.answer, result.backend, result.ms, usage=result.usage)
    resp["x_lima_meta"]["request_type"] = result.request_type
    resp["x_lima_meta"]["skills_injected"] = result.skills_injected
    return resp


def with_injection_meta(result: RouteResult, backend: str = "") -> RouteResult:
    try:
        from context_injection_trace import finish_trace

        trace = finish_trace(backend=backend)
        if trace:
            result.injection_meta = trace.to_meta()
    except ImportError:
        pass
    return result
