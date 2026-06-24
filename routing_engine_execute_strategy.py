"""Execution strategy selection inside routing_engine.route()."""

from __future__ import annotations

import logging
from typing import Callable

import budget_manager
import health_tracker
import speculative
import sticky_session
from routing_executor import execute

_log = logging.getLogger(__name__)


def execute_with_strategy(
    call_fn: Callable,
    backends: list[str],
    messages: list[dict],
    max_tokens: int,
    query: str,
    req_type: str,
    scenario: str,
    needs_tools: bool,
    tools: list[dict] | None,
    sticky_key: str,
) -> tuple[str, str]:
    """根据复杂度选择执行策略（投机/标准），返回 (backend, answer)。"""
    complexity = speculative.classify_complexity(query, messages)

    if needs_tools:
        final_backend, answer = _run_standard_execute(
            backends, call_fn, messages, max_tokens, scenario, req_type, tools=tools
        )
    elif complexity == "simple" and req_type in ("ide", "chat"):
        final_backend, answer = _try_speculative(backends, call_fn, messages, max_tokens, scenario, req_type)
    else:
        final_backend, answer = _run_standard_execute(backends, call_fn, messages, max_tokens, scenario, req_type)

    if final_backend != "exhausted":
        sticky_session.pin_backend(sticky_key, final_backend)

    return final_backend, answer


def _run_standard_execute(
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    request_type: str,
    tools: list[dict] | None = None,
) -> tuple[str, str]:
    """调用模块级 execute 并丢弃第三返回值。"""
    final_backend, answer, _ = execute(
        backends,
        call_fn,
        messages,
        max_tokens,
        tools=tools,
        scenario=scenario,
        request_type=request_type,
    )
    return final_backend, answer


def _try_speculative(
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    req_type: str,
) -> tuple[str, str]:
    """尝试投机执行，回退到标准执行。"""
    affinity_backends = speculative.get_affinity_backends("simple")
    spec_candidates = [
        b
        for b in affinity_backends
        if not health_tracker.is_cooled_down(b)
        and budget_manager.is_budget_available(b)
        and speculative.is_historically_fast(b)
    ]
    if len(spec_candidates) >= 2:
        try:
            return speculative.speculative_call(
                spec_candidates,
                call_fn,
                messages,
                max_tokens,
                max_parallel=5,
                timeout_sec=5.0,
                scenario=scenario,
                request_type=req_type,
            )[:2]
        except RuntimeError:
            pass
    final_backend, answer, _ = execute(
        backends,
        call_fn,
        messages,
        max_tokens,
        scenario=scenario,
        request_type=req_type,
    )
    return final_backend, answer
