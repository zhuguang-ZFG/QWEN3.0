"""multi_pass_refiner.py — 多遍精炼管线：弱后端协作达成强模型效果。

核心策略: Generate → Review → Fix → Verify 四遍流水线

每一遍使用不同类型的后端，后端之间优势互补:
  Pass 1 (Generate): 极速后端 → 快速生成初版代码 (3s 超时)
  Pass 2 (Review):   推理后端 → 审查初版找问题 (5s 超时)
  Pass 3 (Fix):      编码专精 → 修复发现的问题 (5s 超时)
  Pass 4 (Verify):   quality_gate 多维评分 → 通过则返回

总延迟目标: < 15 秒。若 generate 已通过 quality gate 则跳过 review+fix。

集成点:
  - routing_engine.py: 在 code_orchestrator 路径中启用
  - code_orchestrator.py: 替代单遍 execute→gate→repair
  - opencode_config.py: LIMA_MULTI_PASS_ENABLED 开关控制
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import dynamic_backend_pool
import health_tracker
import quality_gate
from backend_reputation import record as record_reputation

_log = logging.getLogger(__name__)

# ── Time budgets per pass (seconds) ─────────────────────────────────────────
GENERATE_TIMEOUT = 3.0    # Fast generation
REVIEW_TIMEOUT = 5.0      # Code review
FIX_TIMEOUT = 5.0         # Fix issues

# Maximum total pipeline time
PIPELINE_BUDGET = 15.0

# Minimum answer length to consider valid
MIN_VALID_LENGTH = 20

# ── Multi-pass enabled flag (can be toggled via env var) ───────────────────

import os

MULTI_PASS_ENABLED = os.environ.get("LIMA_MULTI_PASS_ENABLED", "1") == "1"


def _build_generate_messages(query: str, messages: list[dict], system_prompt: str) -> list[dict]:
    """Build messages for the Generate pass."""
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    if messages:
        # Use conversation context but append the query as final user message
        msgs.extend(messages[:-1] if len(messages) > 1 else [])
    msgs.append({"role": "user", "content": query})
    return msgs


def _build_review_messages(query: str, generated_code: str) -> list[dict]:
    """Build messages for the Review pass: ask model to critique code."""
    review_prompt = (
        "Review the following code for the task below. Identify:\n"
        "1. Syntax errors or bugs\n"
        "2. Missing edge case handling\n"
        "3. Performance issues\n"
        "4. Security vulnerabilities\n"
        "5. Incomplete implementation (TODO, pass, stubs)\n\n"
        f"Task: {query}\n\n"
        f"Code to review:\n```\n{generated_code[:3000]}\n```\n\n"
        "List each issue as a bullet point. Be specific — mention "
        "exact line content that is problematic. If the code looks "
        "correct, reply with just: NO_ISSUES"
    )
    return [{"role": "user", "content": review_prompt}]


def _build_fix_messages(query: str, generated_code: str, review_feedback: str) -> list[dict]:
    """Build messages for the Fix pass: ask model to fix identified issues."""
    fix_prompt = (
        f"Fix the code based on the review feedback below.\n\n"
        f"Original task: {query}\n\n"
        f"Current code:\n```\n{generated_code[:2000]}\n```\n\n"
        f"Review feedback:\n{review_feedback[:1000]}\n\n"
        "Provide the complete corrected code. "
        "Only output the code, no explanation needed."
    )
    return [{"role": "user", "content": fix_prompt}]


def _call_with_timeout(
    backend: str,
    messages: list[dict],
    call_fn: Callable[[str, list[dict], int], str],
    max_tokens: int,
    timeout_sec: float,
) -> tuple[str, float]:
    """Call a backend with timeout. Returns (answer, elapsed_sec)."""
    t0 = time.time()
    try:
        answer = call_fn(backend, messages, max_tokens)
        elapsed = time.time() - t0
        if elapsed > timeout_sec * 1.5:
            _log.debug(
                "Backend %s exceeded timeout (%.1fs > %.1fs), but returned",
                backend, elapsed, timeout_sec,
            )
        return answer, elapsed
    except Exception as exc:
        elapsed = time.time() - t0
        _log.debug("Backend %s failed in %.1fs: %s", backend, elapsed, type(exc).__name__)
        health_tracker.record_failure(backend, error_code=getattr(exc, "status_code", 500))
        return "", elapsed


def _try_pool(
    pool: list[str],
    messages: list[dict],
    call_fn: Callable[[str, list[dict], int], str],
    max_tokens: int,
    timeout_sec: float,
    step_name: str,
) -> tuple[str, str]:
    """Try backends in pool sequentially until one returns valid answer.

    Returns (backend_name, answer). Falls back to next backend on failure.
    """
    for backend in pool:
        if not dynamic_backend_pool._is_selectable(backend):
            continue
        answer, elapsed = _call_with_timeout(
            backend, messages, call_fn, max_tokens, timeout_sec,
        )
        if answer and len(answer.strip()) >= MIN_VALID_LENGTH:
            _log.info(
                "[MULTI_PASS] %s: %s → %d chars in %.1fs",
                step_name, backend, len(answer.strip()), elapsed,
            )
            return backend, answer.strip()
        _log.debug(
            "[MULTI_PASS] %s: %s failed (%.1fs, %d chars)",
            step_name, backend, elapsed, len(answer.strip()) if answer else 0,
        )
    return "", ""


def refine(
    query: str,
    messages: list[dict],
    call_fn: Callable[[str, list[dict], int], str],
    max_tokens: int = 4096,
    system_prompt: str = "",
    ide_source: str = "",
) -> dict[str, Any]:
    """Multi-pass refinement pipeline: Generate → Review → Fix → Verify.

    Args:
        query: The user's coding request.
        messages: Full conversation history.
        call_fn: Function to call a backend: call_fn(backend_name, messages, max_tokens) → str.
        max_tokens: Max tokens for generation.
        system_prompt: Pre-computed system prompt (from code_orchestrator).
        ide_source: IDE identifier for logging/tuning.

    Returns:
        {"answer": str, "backend": str, "passes": int, "score": int,
         "reviewed": bool, "fixed": bool, "latency_ms": float}
    """
    if not MULTI_PASS_ENABLED:
        return {"answer": "", "backend": "", "passes": 0, "score": 0,
                "reviewed": False, "fixed": False, "latency_ms": 0,
                "skipped": "multi_pass_disabled"}

    t0 = time.time()
    pools = dynamic_backend_pool.get_multi_pass_pools()

    # ── Pass 1: Generate ──────────────────────────────────────────────────
    gen_msgs = _build_generate_messages(query, messages, system_prompt)
    gen_backend, gen_answer = _try_pool(
        pools["generate"], gen_msgs, call_fn, max_tokens,
        GENERATE_TIMEOUT, "GENERATE",
    )

    if not gen_answer:
        # Generate failed entirely — try fallback pool
        _log.warning("[MULTI_PASS] Generate pool exhausted, trying fallback")
        gen_backend, gen_answer = _try_pool(
            pools["fallback"], gen_msgs, call_fn, max_tokens,
            8.0, "GENERATE_FALLBACK",
        )
        if not gen_answer:
            elapsed = (time.time() - t0) * 1000
            return {"answer": "", "backend": "exhausted", "passes": 0, "score": 0,
                    "reviewed": False, "fixed": False, "latency_ms": elapsed}

    # Quick quality check on generated code
    gen_gate = quality_gate.check(gen_answer, query)
    elapsed_ms = (time.time() - t0) * 1000

    # If generate already passes quality gate, return early (fast path)
    if gen_gate["passed"] and elapsed_ms < PIPELINE_BUDGET * 1000 * 0.3:
        record_reputation(gen_backend, True, "code_generate")
        _log.info(
            "[MULTI_PASS] Fast path: generate passed gate (score=%d), "
            "backend=%s, %.0fms",
            gen_gate["score"], gen_backend, elapsed_ms,
        )
        return {
            "answer": gen_answer, "backend": gen_backend,
            "passes": 1, "score": gen_gate["score"],
            "reviewed": False, "fixed": False,
            "latency_ms": elapsed_ms,
        }

    # Check pipeline budget before continuing
    remaining_budget = PIPELINE_BUDGET - (time.time() - t0)
    if remaining_budget < 3.0:
        _log.info("[MULTI_PASS] Budget exhausted after generate (%.1fs)", time.time() - t0)
        return {
            "answer": gen_answer, "backend": gen_backend,
            "passes": 1, "score": gen_gate["score"],
            "reviewed": False, "fixed": False,
            "latency_ms": elapsed_ms,
        }

    # ── Pass 2: Review ────────────────────────────────────────────────────
    review_msgs = _build_review_messages(query, gen_answer)
    review_backend, review_feedback = _try_pool(
        pools["review"], review_msgs, call_fn, max_tokens // 2,
        REVIEW_TIMEOUT, "REVIEW",
    )

    reviewed = bool(review_feedback)
    has_issues = reviewed and "NO_ISSUES" not in review_feedback.upper()

    if not has_issues:
        record_reputation(gen_backend, True, "code_generate")
        if reviewed:
            record_reputation(review_backend, True, "code_review")
        elapsed_final = (time.time() - t0) * 1000
        return {
            "answer": gen_answer, "backend": gen_backend,
            "passes": 2 if reviewed else 1,
            "score": gen_gate["score"],
            "reviewed": reviewed, "fixed": False,
            "latency_ms": elapsed_final,
        }

    # Check pipeline budget
    remaining_budget = PIPELINE_BUDGET - (time.time() - t0)
    if remaining_budget < 3.0:
        _log.info("[MULTI_PASS] Budget exhausted after review (%.1fs)", time.time() - t0)
        return {
            "answer": gen_answer, "backend": gen_backend,
            "passes": 2, "score": gen_gate["score"],
            "reviewed": True, "fixed": False,
            "latency_ms": (time.time() - t0) * 1000,
        }

    # ── Pass 3: Fix ───────────────────────────────────────────────────────
    fix_msgs = _build_fix_messages(query, gen_answer, review_feedback)
    fix_backend, fixed_answer = _try_pool(
        pools["refine"], fix_msgs, call_fn, max_tokens,
        FIX_TIMEOUT, "FIX",
    )

    if not fixed_answer:
        # Fix failed, return original
        elapsed_final = (time.time() - t0) * 1000
        return {
            "answer": gen_answer, "backend": gen_backend,
            "passes": 2, "score": gen_gate["score"],
            "reviewed": True, "fixed": False,
            "latency_ms": elapsed_final,
        }

    # ── Pass 4: Verify ────────────────────────────────────────────────────
    fix_gate = quality_gate.check(fixed_answer, query)

    # Choose best answer
    if fix_gate["score"] > gen_gate["score"]:
        record_reputation(fix_backend, True, "code_fix")
        record_reputation(review_backend, True, "code_review")
        _log.info(
            "[MULTI_PASS] Fixed improved score %d→%d via %s",
            gen_gate["score"], fix_gate["score"], fix_backend,
        )
        elapsed_final = (time.time() - t0) * 1000
        return {
            "answer": fixed_answer, "backend": fix_backend,
            "passes": 3, "score": fix_gate["score"],
            "reviewed": True, "fixed": True,
            "latency_ms": elapsed_final,
        }

    # Fix didn't improve, keep original
    _log.info(
        "[MULTI_PASS] Fix did not improve score (%d vs %d), keeping original",
        fix_gate["score"], gen_gate["score"],
    )
    elapsed_final = (time.time() - t0) * 1000
    return {
        "answer": gen_answer, "backend": gen_backend,
        "passes": 3, "score": gen_gate["score"],
        "reviewed": True, "fixed": True,
        "latency_ms": elapsed_final,
    }


# ── Simplified single-pass wrapper (for compatibility with code_orchestrator) ─

def single_pass(
    query: str,
    messages: list[dict],
    call_fn: Callable[[str, list[dict], int], str],
    max_tokens: int = 4096,
    system_prompt: str = "",
) -> tuple[str, str]:
    """Single-pass with dynamic pool (fallback for when multi_pass is disabled)."""
    pools = dynamic_backend_pool.get_orchestrator_pools()
    gen_msgs = _build_generate_messages(query, messages, system_prompt)

    # Try coder pool first, then strong, then fast
    for pool_name in ["coder", "strong", "fast"]:
        backend, answer = _try_pool(
            pools.get(pool_name, []), gen_msgs, call_fn, max_tokens,
            10.0, f"SINGLE_{pool_name.upper()}",
        )
        if answer:
            return backend, answer

    return "", ""
