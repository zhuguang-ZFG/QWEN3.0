"""orchestrate.py — 1+N >> N 编排器 facade.

复杂任务拆解为子任务，每个子任务路由到最强专业模型，合并结果。
实现细节见 orchestrate_detect / orchestrate_pipeline。
"""

from __future__ import annotations

import time

import http_caller
import routing_engine
import routing_intent
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
    "http_caller",
    "routing_engine",
]


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
    """编排入口：复杂任务拆解 → 并发执行 → 合并结果。"""
    t0 = time.time()

    intent = routing_intent.analyze_intent(query, system_prompt=system_prompt, ide=ide_source)

    if not needs_orchestration(query, intent):
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

    subtasks = decompose(query)

    if len(subtasks) == 1 and subtasks[0]["task"] == query:
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

    results = execute_subtasks(
        subtasks,
        ide_source=ide_source,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )

    final_answer = synthesize(query, results)

    backends_used = list({r["backend"] for r in results})
    total_ms = int((time.time() - t0) * 1000)
    subtask_ms = [r["ms"] for r in results]

    return {
        "answer": final_answer,
        "backend": f"orchestrate({','.join(backends_used)})",
        "intent": intent,
        "total_ms": total_ms,
        "orchestration": {
            "subtask_count": len(subtasks),
            "backends_used": backends_used,
            "subtask_ms": subtask_ms,
            "parallel_speedup": f"{sum(subtask_ms) / max(max(subtask_ms), 1):.1f}x",
        },
    }


if __name__ == "__main__":
    print("=== orchestrate.py 单元测试 ===\n")

    simple_intent = {"intent": "grbl_config", "complexity": 0.3}
    assert not needs_orchestration("GRBL怎么设置", simple_intent), "简单查询不应触发编排"

    complex_intent = {"intent": "unknown", "complexity": 0.9}
    complex_q = "请分别从硬件电路设计和软件编程两个角度，分析步进电机丢步问题的原因和解决方案"
    assert needs_orchestration(complex_q, complex_intent), "跨领域复杂查询应触发编排"
    print("[PASS] needs_orchestration 判断正确")

    fallback = decompose("简单问题")
    assert len(fallback) >= 1, "decompose 应至少返回1个子任务"
    assert fallback[0]["task"] == "简单问题", "解析失败应回退为原查询"
    print("[PASS] decompose 回退逻辑正确")

    print("\n=== 所有测试通过 ===")
