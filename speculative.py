"""
LiMa Speculative Execution — 并行投机调用

简单问题同时发 N 个快速后端，谁先返回有效响应就用谁。
- 降低用户感知延迟（取最快后端的延迟）
- 充分利用免费后端配额
- 复杂问题不并行（避免浪费付费配额）
"""

import time
import asyncio
import threading
import logging
import queue as queue_mod
from typing import Callable, Optional

import health_tracker
import budget_manager

logger = logging.getLogger("speculative")

# 最小有效响应长度
MIN_VALID_LENGTH = 10


def speculative_call(
    backends: list[str],
    call_fn: Callable[[str, list[dict], int], str],
    messages: list[dict],
    max_tokens: int = 4096,
    max_parallel: int = 3,
    timeout_sec: float = 3.0,
) -> tuple[str, str, float]:
    """并行调用多个后端，返回第一个有效响应。

    Uses asyncio internally via speculative_call_async,
    wrapping call_fn with asyncio.to_thread.

    Returns: (backend_name, answer, latency_ms)
    Raises: RuntimeError if all backends fail within timeout
    """
    async def _wrap_sync(b: str, m: list[dict], mt: int) -> str:
        return await asyncio.to_thread(call_fn, b, m, mt)

    try:
        return _run_coro_sync(speculative_call_async(
            backends, _wrap_sync, messages, max_tokens,
            max_parallel=max_parallel, timeout_sec=timeout_sec,
        ))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Speculative execution failed: {e}") from e


def _run_coro_sync(coro):
    """Run a coroutine for the sync facade, even if called inside an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_q: queue_mod.Queue = queue_mod.Queue(maxsize=1)

    def _runner():
        try:
            result_q.put((True, asyncio.run(coro)))
        except Exception as exc:
            result_q.put((False, exc))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    ok, value = result_q.get()
    if ok:
        return value
    raise value


async def speculative_call_async(
    backends: list[str],
    async_call_fn: Callable[[str, list[dict], int], object],
    messages: list[dict],
    max_tokens: int = 4096,
    max_parallel: int = 3,
    timeout_sec: float = 3.0,
) -> tuple[str, str, float]:
    """Async-native speculative execution using asyncio.create_task.

    Returns: (backend_name, answer, latency_ms)
    Raises: RuntimeError if all backends fail within timeout
    """
    candidates = backends[:max_parallel]
    if not candidates:
        raise RuntimeError("No backends available for speculative execution")

    t0 = time.time()
    tasks: dict[asyncio.Task, str] = {}

    async def _worker(backend: str) -> str:
        backend_t0 = time.time()
        try:
            result = await async_call_fn(backend, messages, max_tokens)
            latency = (time.time() - backend_t0) * 1000
            _record_latency(backend, latency)
            if isinstance(result, str):
                return result
            return ""
        except Exception as e:
            latency = (time.time() - backend_t0) * 1000
            health_tracker.record_failure(
                backend, error_code=getattr(e, 'status_code', 500))
            _record_latency(backend, latency + _SLOW_THRESHOLD_MS)
            logger.debug(f"[SPEC_ASYNC] {backend} failed: {type(e).__name__}")
            return ""

    for backend in candidates:
        tasks[asyncio.create_task(_worker(backend))] = backend

    winner_backend = ""
    winner_answer = ""
    pending = set(tasks.keys())
    deadline = time.monotonic() + timeout_sec
    try:
        while pending and not winner_backend:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = await asyncio.wait(
                pending, timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                break
            for task in done:
                try:
                    answer = task.result()
                except Exception:
                    continue
                if answer and len(answer.strip()) >= MIN_VALID_LENGTH:
                    winner_backend = tasks[task]
                    winner_answer = answer
                    break

        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    except Exception:
        pass

    if not winner_backend:
        raise RuntimeError("All speculative backends failed or returned empty")

    latency_ms = (time.time() - t0) * 1000
    health_tracker.record_success(winner_backend, latency_ms)
    budget_manager.record_usage(winner_backend)
    logger.info(f"[SPEC] winner={winner_backend} latency={latency_ms:.0f}ms "
                f"(tried {len(candidates)} backends)")
    return winner_backend, winner_answer, latency_ms


# ── 延迟学习 — 自动排除慢后端 ────────────────────────────────────────────────

_latency_lock = threading.Lock()
_latency_history: dict[str, list[float]] = {}
_LATENCY_WINDOW = 10
_SLOW_THRESHOLD_MS = 4000


def _record_latency(backend: str, latency_ms: float):
    """记录后端实际响应延迟。"""
    with _latency_lock:
        if backend not in _latency_history:
            _latency_history[backend] = []
        _latency_history[backend].append(latency_ms)
        if len(_latency_history[backend]) > _LATENCY_WINDOW:
            _latency_history[backend] = _latency_history[backend][-_LATENCY_WINDOW:]


def is_historically_fast(backend: str) -> bool:
    """后端历史平均延迟是否在阈值内。无历史数据默认允许。"""
    with _latency_lock:
        history = _latency_history.get(backend)
        if not history or len(history) < 3:
            return True
        avg = sum(history) / len(history)
        return avg < _SLOW_THRESHOLD_MS


# ── 查询复杂度判断 ───────────────────────────────────────────────────────────

def classify_complexity(query: str, messages: list[dict]) -> str:
    """
    判断请求复杂度: 'simple' | 'code' | 'complex'
    - simple: 短问题、打招呼、简单问答 → 并行投机
    - code: 代码相关 → 走代码专用后端
    - complex: 长文分析、多轮深度对话 → 走 premium
    """
    query_len = len(query)
    total_context = sum(len(m.get("content", "")) for m in messages
                        if isinstance(m.get("content"), str))

    # 代码关键词检测（优先于长度判断）
    code_signals = [
        "代码", "code", "函数", "function", "bug", "error", "fix",
        "def ", "class ", "import ", "```", "compile", "debug",
        "实现", "implement", "refactor", "重构", "优化",
        "TypeError", "ValueError", "Exception", "traceback",
    ]
    query_lower = query.lower()
    if any(kw in query_lower for kw in code_signals):
        return "code"

    # 长上下文 = complex
    if total_context > 3000 or query_len > 500:
        return "complex"

    # 多轮对话（>4轮）= complex
    if len(messages) > 8:
        return "complex"

    # 短问题 = simple
    if query_len < 80 and total_context < 500:
        return "simple"

    return "simple"


# ── 后端亲和映射 ─────────────────────────────────────────────────────────────

AFFINITY = {
    "simple_fast": [
        "longcat_lite", "longcat_chat", "google_flash",
        "groq_llama70b", "cerebras_gptoss", "cf_llama70b",
        "cf_qwen3_30b", "cf_gemma4", "ovh_llama70b",
        "groq_qwen32b", "nvidia_nemotron", "nvidia_llama70b",
        "sambanova_llama4", "deepinfra_llama4",
        "groq_llama4", "groq_gptoss", "google_flash_lite", "google_gemma4", "github_gpt4o_mini",
    ],
    "code": [
        "nvidia_qwen_coder", "cf_qwen_coder",
        "opencode_stealth", "mistral_devstral",
        "groq_llama70b", "cerebras_gptoss",
        "github_codestral", "or_qwen3_coder", "mistral_codestral",
    ],
    "complex_premium": [
        "longcat", "longcat_thinking",
        "fireworks_llama405b", "cf_kimi_k26", "mistral_large",
        "nvidia_qwen_coder",
    ],
}


def get_affinity_backends(complexity: str) -> list[str]:
    """根据复杂度返回亲和后端列表（能力矩阵驱动 + 随机轮转）。"""
    import random
    try:
        import capability_matrix
        intent = {
            "simple": "english",
            "code": "code",
            "complex": "reasoning",
        }.get(complexity, "english")
        pool = capability_matrix.select_backends(intent, top_n=12)
    except Exception:
        # Fallback to static AFFINITY if capability_matrix fails
        if complexity == "simple":
            pool = list(AFFINITY["simple_fast"])
        elif complexity == "code":
            pool = list(AFFINITY["code"])
        else:
            pool = list(AFFINITY["complex_premium"])
    random.shuffle(pool)
    return pool
