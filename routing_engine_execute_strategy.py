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
    """根据复杂度选择执行策略（投机/代码优先/标准），返回 (backend, answer)。"""
    complexity = speculative.classify_complexity(query, messages)

    if needs_tools:
        final_backend, answer, _ = execute(
            backends,
            call_fn,
            messages,
            max_tokens,
            tools=tools,
            scenario=scenario,
            request_type=req_type,
        )
    elif complexity == "simple" and req_type in ("ide", "chat"):
        final_backend, answer = _try_speculative(
            backends,
            call_fn,
            messages,
            max_tokens,
            scenario,
            req_type,
        )
    elif complexity == "code":
        final_backend, answer = _execute_code_priority(
            backends,
            call_fn,
            messages,
            max_tokens,
            scenario,
            req_type,
        )
    else:
        final_backend, answer, _ = execute(
            backends,
            call_fn,
            messages,
            max_tokens,
            scenario=scenario,
            request_type=req_type,
        )

    if final_backend != "exhausted":
        sticky_session.pin_backend(sticky_key, final_backend)

    if answer and scenario == "coding":
        final_backend, answer = _maybe_quality_retry(
            final_backend,
            answer,
            backends,
            call_fn,
            messages,
            max_tokens,
            query,
            scenario,
            req_type,
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


def _execute_code_priority(
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    req_type: str,
) -> tuple[str, str]:
    """代码场景优先使用 code affinity 后端。"""
    code_backends = speculative.get_affinity_backends("code")
    code_available = [
        b for b in code_backends if not health_tracker.is_cooled_down(b) and budget_manager.is_budget_available(b)
    ]
    merged = code_available + [b for b in backends if b not in code_available]
    final_backend, answer, _ = execute(
        merged,
        call_fn,
        messages,
        max_tokens,
        scenario=scenario,
        request_type=req_type,
    )
    return final_backend, answer


def _maybe_quality_retry(
    final_backend: str,
    answer: str,
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    query: str,
    scenario: str,
    req_type: str,
) -> tuple[str, str]:
    """coding 场景质量验证不通过时自动重试。"""
    try:
        from context_pipeline.response_validator import validate_response

        vr = validate_response(answer, query)
        if not vr.passed and len(backends) > 1:
            retry_backends = [b for b in backends if b != final_backend][:2]
            if retry_backends:
                _log.info(
                    "response validation failed (score=%.2f, issues=%s), retrying with %s",
                    vr.score,
                    vr.issues[:3],
                    retry_backends,
                )
                retry_backend, retry_answer, _ = execute(
                    retry_backends,
                    call_fn,
                    messages,
                    max_tokens,
                    scenario=scenario,
                    request_type=req_type,
                )
                if retry_answer:
                    vr2 = validate_response(retry_answer, query)
                    if vr2.score > vr.score:
                        try:
                            health_tracker.record_failure(final_backend, 200, "quality_retry")
                        except Exception as exc:
                            _log.debug(
                                "quality retry health record failed: %s",
                                type(exc).__name__,
                            )
                        return retry_backend, retry_answer
    except Exception as exc:
        _log.debug("response validation retry failed: %s", type(exc).__name__)
    return final_backend, answer
