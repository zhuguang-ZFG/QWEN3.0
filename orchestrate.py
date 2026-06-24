# DEPRECATED v3.0 — coding capability retired
"""orchestrate.py — 1+N >> N 编排器 facade.

复杂任务拆解为子任务，每个子任务路由到最强专业模型，合并结果。
实现细节见 orchestrate_detect / orchestrate_pipeline。

DEPRECATED: the multi-model orchestrator was retired in v3.0 together with the
coding capability.  The module now acts as a transparent passthrough to the
routing engine so existing imports and calls continue to work.
"""

from __future__ import annotations

from orchestrate_detect import needs_orchestration
from orchestrate_pipeline import (
    _route_via_engine,
    decompose,
    execute_subtasks,
    synthesize,
)

# Re-export for tests and backward-compatible monkeypatch targets.
__all__ = [
    "needs_orchestration",
    "decompose",
    "execute_subtasks",
    "synthesize",
    "orchestrate",
    "_route_via_engine",
]


def _direct_route(
    query: str,
    messages: list[dict] | None,
    ide_source: str,
    system_prompt: str,
    max_tokens: int,
    needs_tools: bool,
    tools: list[dict] | None,
) -> dict:
    """Route a query directly through the engine and return the standard result dict."""
    r = _route_via_engine(
        query,
        messages=messages,
        ide_source=ide_source,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        needs_tools=needs_tools,
        tools=tools,
    )
    return {"answer": r.answer, "backend": r.backend, "total_ms": r.ms}


def orchestrate(
    query: str,
    *,
    messages: list[dict] | None = None,
    ide_source: str = "",
    system_prompt: str = "",
    max_tokens: int = 4096,
    needs_tools: bool = False,
    tools: list[dict] | None = None,
) -> dict:
    """编排入口：复杂任务拆解 → 并发执行 → 合并结果。

    Deprecated: always routes directly through the engine.  Orchestration was
    retired in v3.0.
    """
    return _direct_route(query, messages, ide_source, system_prompt, max_tokens, needs_tools, tools)


if __name__ == "__main__":
    print("=== orchestrate.py deprecated passthrough ===")
    print("needs_orchestration always returns:", needs_orchestration("test", {}))
    print("decompose fallback:", decompose("hello"))
    print("execute_subtasks fallback:", execute_subtasks([{"task": "hello"}]))
    print("synthesize fallback:", synthesize("hello", []))
