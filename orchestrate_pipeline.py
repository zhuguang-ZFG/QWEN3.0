"""Decompose, execute, synthesize, and route helpers for orchestration."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import health_tracker
import http_caller
import routing_engine
from backends_registry import BACKENDS
from orchestrate_constants import (
    DECOMPOSE_MAX_TOKENS,
    LOCAL_ROUTER_URL,
    MAX_CONCURRENT,
    SYNTHESIZE_MAX_TOKENS,
)

_log = logging.getLogger(__name__)


def _call_local_router(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
    """Call the local router model (Ollama-compatible) for decomposition/synthesis."""
    import urllib.request

    payload = json.dumps(
        {
            "model": "local-model",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        request = urllib.request.Request(
            LOCAL_ROUTER_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        return f"[LOCAL_ERR] {exc}"


def decompose(query: str) -> list[dict[str, Any]]:
    """Split a complex query into independent subtasks."""
    prompt = (
        "你是一个任务拆解专家。将以下复杂问题拆解为2-4个独立子任务。\n"
        "每个子任务应该可以独立回答，合并后能完整解决原问题。\n\n"
        f"问题：{query[:800]}\n\n"
        "输出 JSON 数组，每个元素包含：\n"
        '- "task": 子任务描述（具体、可独立回答）\n'
        '- "domain": 领域（hardware/software/mechanical/theory/general）\n'
        '- "backend_hint": 建议后端（留空则自动路由）\n\n'
        "只输出 JSON，不要其他文字。"
    )
    resp = _call_local_router(
        [{"role": "user", "content": prompt}],
        max_tokens=DECOMPOSE_MAX_TOKENS,
        temperature=0.3,
    )

    try:
        text = resp.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            subtasks = json.loads(text[start:end])
            valid = []
            for st in subtasks[:4]:
                if isinstance(st, dict) and "task" in st:
                    valid.append(
                        {
                            "task": st["task"],
                            "domain": st.get("domain", "general"),
                            "backend_hint": st.get("backend_hint", ""),
                        }
                    )
            if valid:
                return valid
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

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


def _exec_subtask(
    idx: int,
    subtask: dict[str, Any],
    *,
    ide_source: str,
    system_prompt: str,
    max_tokens: int,
) -> dict[str, Any]:
    """Execute a single subtask via hinted backend or routing engine."""
    t0 = time.time()
    task_query = subtask["task"]
    hint = subtask.get("backend_hint", "")

    if hint and hint in BACKENDS and not health_tracker.is_cooled_down(hint):
        try:
            answer = http_caller.call_api(
                hint,
                [{"role": "user", "content": task_query}],
                max_tokens,
                system_prompt=system_prompt,
                ide=ide_source,
            )
            return {"task": task_query, "answer": answer, "backend": hint, "ms": int((time.time() - t0) * 1000)}
        except Exception as exc:
            _log.warning("orchestrate hint backend failed hint=%s: %s", hint, exc)

    r = _route_via_engine(
        task_query,
        messages=[{"role": "user", "content": task_query}],
        ide_source=ide_source,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )
    return {"task": task_query, "answer": r.answer, "backend": r.backend, "ms": int((time.time() - t0) * 1000)}


def execute_subtasks(
    subtasks: list[dict[str, Any]],
    *,
    ide_source: str = "",
    system_prompt: str = "",
    max_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Run subtasks concurrently via routing_engine or hinted backends."""
    results: list[dict[str, Any]] = [
        {"task": st.get("task", ""), "answer": "", "backend": "pending", "ms": 0} for st in subtasks
    ]

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = {
            executor.submit(
                _exec_subtask, i, st, ide_source=ide_source, system_prompt=system_prompt, max_tokens=max_tokens
            ): i
            for i, st in enumerate(subtasks)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {
                    "task": subtasks[idx]["task"],
                    "answer": f"[\u5b50\u4efb\u52a1\u6267\u884c\u5931\u8d25: {e}]",
                    "backend": "error",
                    "ms": 0,
                }

    return results


def synthesize(query: str, results: list[dict[str, Any]]) -> str:
    """Merge subtask answers into one coherent response."""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"【子任务{i}】{r['task']}\n【回答{i}】{r['answer']}")
    combined = "\n\n".join(parts)

    prompt = (
        "你是一个专业的技术文档整合专家。\n"
        "用户提出了一个复杂问题，已被拆解为多个子任务并分别回答。\n"
        "请将以下子任务回答整合为一个连贯、完整、结构清晰的最终回答。\n"
        "要求：去除重复内容，保持逻辑顺序，使用中文。\n\n"
        f"用户原始问题：{query[:500]}\n\n"
        f"子任务回答：\n{combined[:3000]}\n\n"
        "请输出整合后的最终回答："
    )

    msgs = [{"role": "user", "content": prompt}]
    try:
        answer = http_caller.call_api(
            "longcat_chat",
            msgs,
            max_tokens=SYNTHESIZE_MAX_TOKENS,
        )
        if answer and "暂时不可用" not in answer:
            return answer
    except Exception as exc:
        _log.warning("orchestrate synthesize longcat failed: %s", exc)

    answer = _call_local_router(msgs, max_tokens=SYNTHESIZE_MAX_TOKENS, temperature=0.5)
    if answer and not answer.startswith("[LOCAL_ERR]"):
        return answer

    return "\n\n".join(r["answer"] for r in results if r["answer"])
