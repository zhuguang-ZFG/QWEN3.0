"""Post-route hooks for routing_engine.route()."""

from __future__ import annotations

import logging

from response_builder import make_chat_id
from route_post_process import apply_post_route_integrations

_log = logging.getLogger(__name__)


def post_route(
    answer: str | None,
    final_backend: str,
    backends: list[str],
    messages_injected: list[dict],
    messages: list[dict],
    req_type: str,
    scenario: str,
    ms: int,
) -> None:
    """路由后处理：post-route 集成、事件记录、反馈闭环。"""
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

    fallback_used = bool(
        final_backend not in ("exhausted", "none") and backends and final_backend != backends[0],
    )
    success = bool(answer and len(answer) > 5)

    try:
        from routes.agent_events import record_event

        record_event(
            "routing_decision",
            {
                "backend": final_backend,
                "scenario": scenario,
                "req_type": req_type,
                "latency_ms": ms,
                "success": success,
                "fallback_used": fallback_used,
            },
        )
    except Exception as exc:
        _log.debug("routing_decision event record failed: %s", type(exc).__name__)

    try:
        from routing_loop.feedback_bridge import on_request_complete

        on_request_complete(
            request_id=make_chat_id(),
            scenario=scenario,
            messages=messages,
            backend=final_backend,
            success=success,
            latency_ms=float(ms),
            fallback_used=fallback_used,
        )
    except Exception as _fb_exc:
        _log.warning("feedback_bridge error: %s", _fb_exc)


def get_injected_ids(original: list[dict], modified: list[dict]) -> list[str]:
    """提取被注入的 skill ID"""
    if len(modified) <= len(original):
        return []
    for msg in modified:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if "Available skills:" in content:
                names = content.replace("Available skills:", "").strip()
                return ["dir:" + n.strip() for n in names.split(",") if n.strip()]
    extra = len(modified) - len(original)
    return [f"injected_{extra}_skills"] if extra > 0 else []
