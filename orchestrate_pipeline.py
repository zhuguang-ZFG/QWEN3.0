# DEPRECATED v3.0 — coding capability retired
"""Decompose, execute, synthesize, and route helpers for orchestration.

DEPRECATED: the multi-model orchestrator was retired in v3.0.  Only the
``_route_via_engine`` passthrough is preserved so that existing callers can
still fall back to a direct route without crashing.
"""

from __future__ import annotations

import logging
from typing import Any

import http_caller
import routing_engine

_log = logging.getLogger(__name__)


def decompose(query: str) -> list[dict[str, Any]]:
    """Split a complex query into independent subtasks.

    Deprecated: returns a single fallback subtask containing the original query.
    """
    return [{"task": query, "domain": "general", "backend_hint": ""}]


def _route_via_engine(
    query: str,
    *,
    messages: list[dict] | None = None,
    ide_source: str = "",
    system_prompt: str = "",
    max_tokens: int = 4096,
    needs_tools: bool = False,
    tools: list[dict] | None = None,
):
    msgs = messages if messages else [{"role": "user", "content": query}]

    def _call_fn(backend, msgs, mt, tools=None):
        return http_caller.call_api(
            backend,
            msgs,
            mt,
            system_prompt=system_prompt,
            ide=ide_source,
            tools=tools,
        )

    return routing_engine.route(
        query,
        msgs,
        fmt="openai",
        ide_source=ide_source,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        call_fn=_call_fn,
        needs_tools=needs_tools,
        tools=tools,
    )


def execute_subtasks(
    subtasks: list[dict[str, Any]],
    *,
    ide_source: str = "",
    system_prompt: str = "",
    max_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Run subtasks concurrently via routing_engine or hinted backends.

    Deprecated: returns a single empty placeholder result because the
    orchestrator was retired in v3.0.
    """
    return [
        {"task": st.get("task", ""), "answer": "", "backend": "deprecated", "ms": 0}
        for st in subtasks
    ]


def synthesize(query: str, results: list[dict[str, Any]]) -> str:
    """Merge subtask answers into one coherent response.

    Deprecated: returns an empty string.  Callers should fall back to the
    direct routing result instead.
    """
    return ""
