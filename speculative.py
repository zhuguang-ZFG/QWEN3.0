"""
LiMa Speculative Execution — 并行投机调用

简单问题同时发 N 个快速后端，谁先返回有效响应就用谁。
- 降低用户感知延迟（取最快后端的延迟）
- 充分利用免费后端配额
- 复杂问题不并行（避免浪费付费配额）
"""

import time
import threading
import logging
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

import health_tracker
import budget_manager

logger = logging.getLogger("speculative")

# 并行执行器（复用线程池，避免频繁创建线程）
_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="spec")

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
    """
    并行调用多个后端，返回第一个有效响应。
    timeout_sec: 硬超时，超过则立即返回已有最佳结果或抛异常。

    Returns: (backend_name, answer, latency_ms)
    Raises: RuntimeError if all backends fail within timeout
    """
    candidates = backends[:max_parallel]
    if not candidates:
        raise RuntimeError("No backends available for speculative execution")

    t0 = time.time()
    futures: dict[Future, str] = {}

    for backend in candidates:
        fut = _executor.submit(_safe_call, call_fn, backend, messages, max_tokens)
        futures[fut] = backend

    # 谁先返回有效响应就用谁，硬超时保护
    winner_backend = ""
    winner_answer = ""

    try:
        for fut in as_completed(futures, timeout=timeout_sec):
            backend = futures[fut]
            try:
                answer = fut.result(timeout=0.1)
            except Exception:
                continue
            if answer and len(answer.strip()) >= MIN_VALID_LENGTH:
                winner_backend = backend
                winner_answer = answer
                break
    except (TimeoutError, Exception):
        pass

    # 取消未完成的 futures（best effort，不阻塞）
    for fut in futures:
        if not fut.done():
            fut.cancel()

    if not winner_backend:
        raise RuntimeError("All speculative backends failed or returned empty")

    latency_ms = (time.time() - t0) * 1000
    health_tracker.record_success(winner_backend, latency_ms)
    budget_manager.record_usage(winner_backend)
    logger.info(f"[SPEC] winner={winner_backend} latency={latency_ms:.0f}ms "
                f"(tried {len(candidates)} backends)")
    return winner_backend, winner_answer, latency_ms


def _safe_call(call_fn, backend: str, messages: list[dict], max_tokens: int) -> str:
    """单个后端调用，异常返回空字符串。记录延迟供学习。"""
    t0 = time.time()
    try:
        result = call_fn(backend, messages, max_tokens)
        latency = (time.time() - t0) * 1000
        _record_latency(backend, latency)
        return result
    except Exception as e:
        latency = (time.time() - t0) * 1000
        health_tracker.record_failure(backend, error_code=getattr(e, 'status_code', 500))
        _record_latency(backend, latency + _SLOW_THRESHOLD_MS)
        return ""


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
        "nvidia_qwen_coder", "cf_qwen_coder", "deepseek_flash",
        "opencode_stealth", "mistral_devstral", "deepseek_pro",
        "groq_llama70b", "cerebras_gptoss",
        "github_codestral", "or_qwen3_coder", "mistral_codestral",
    ],
    "complex_premium": [
        "longcat", "longcat_thinking", "deepseek_pro",
        "fireworks_llama405b", "cf_kimi_k26", "mistral_large",
        "nvidia_qwen_coder", "deepseek_flash",
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
