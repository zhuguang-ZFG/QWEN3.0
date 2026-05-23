"""routes/quality_gate.py — 质量检查与 fallback 逻辑

从 server.py 提取的质量门控函数：
- 回答质量检查
- 同层/升级 fallback 选择
- 默认路由
- 单后端调用
- 失败响应构建
"""
import asyncio
import logging
import threading

import smart_router
import http_caller
from response_builder import build_response, build_anthropic_response, MODEL_ID

# ── Shared state (injected from server.py) ────────────────────────────────────
_backend_enabled: dict = {}


def inject_state(backend_enabled: dict) -> None:
    """Called once from server.py to wire in shared mutable state."""
    global _backend_enabled
    _backend_enabled = backend_enabled


# ── Backend Tiers ─────────────────────────────────────────────────────────────
BACKEND_TIERS = {
    "L1_free": ["longcat_lite", "longcat_chat", "longcat", "longcat_thinking", "longcat_omni", "chinamobile"],
    "L2_nvidia": ["nvidia_qwen_coder", "nvidia_nemotron", "nvidia_phi4", "nvidia_llama4", "nvidia_llama70b", "nvidia_mistral"],
    "L2_openrouter": ["or_deepseek_r1", "or_qwen3_coder", "or_llama70b", "or_nemotron", "or_qwen3_80b"],
    "L3_paid": [],
}

# ── Exact Output Markers ──────────────────────────────────────────────────────
EXACT_OUTPUT_MARKERS = (
    "return exactly",
    "respond exactly",
    "output exactly",
    "print exactly",
    "exactly:",
    "only return",
    "only output",
    "只返回",
    "只输出",
    "仅返回",
    "仅输出",
)


# ── Tier / Upgrade helpers ────────────────────────────────────────────────────

def get_same_tier_backends(current_backend: str) -> list:
    """获取同层级的其他后端（排除当前的）。"""
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            return [b for b in backends if b != current_backend]
    return []


def get_upgrade_chain(current_backend: str) -> list:
    """获取升级链：当前层级之上的所有后端。"""
    tiers = list(BACKEND_TIERS.keys())
    current_tier = None
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            current_tier = tier
            break
    if not current_tier:
        return ["longcat_chat"]  # 默认 fallback
    tier_idx = tiers.index(current_tier)
    upgrade_backends = []
    for tier in tiers[tier_idx + 1:]:
        upgrade_backends.extend(BACKEND_TIERS[tier][:2])  # 每层取前2个
    return upgrade_backends


def default_route(query: str, ide: str = "unknown") -> str:
    """当路由模型输出无效时，用简单规则选后端。"""
    query_len = len(query)
    # 短问题用快速后端
    if query_len < 50:
        return "longcat_lite"
    # 代码相关关键词
    code_keywords = ["代码", "code", "函数", "function", "bug", "error", "def ", "class ", "import "]
    if any(kw in query.lower() for kw in code_keywords):
        return "nvidia_qwen_coder"
    # 长问题用通用后端
    if query_len > 200:
        return "longcat"
    # 默认
    return "longcat_chat"


# ── Quality Check helpers ─────────────────────────────────────────────────────

def allows_short_direct_answer(query: str, response_text: str) -> bool:
    if not query or not response_text:
        return False
    lowered = query.lower()
    if not any(marker in lowered for marker in EXACT_OUTPUT_MARKERS):
        return False
    return 1 <= len(response_text.strip()) <= 120


def _strip_direct_answer(value: str) -> str:
    return value.strip().strip("\"'`“”‘’")


def expected_direct_answer(query: str) -> str:
    if not query:
        return ""
    lowered = query.lower()
    for marker in (
        "return exactly",
        "respond exactly",
        "output exactly",
        "print exactly",
        "only return",
        "only output",
    ):
        idx = lowered.rfind(marker)
        if idx < 0:
            continue
        rest = query[idx + len(marker):].strip()
        if not rest or rest[0] not in (":", "："):
            continue
        candidate = _strip_direct_answer(rest[1:])
        if candidate and "\n" not in candidate and len(candidate) <= 120:
            return candidate
    for marker in ("只返回", "只输出", "仅返回", "仅输出"):
        idx = query.rfind(marker)
        if idx < 0:
            continue
        rest = query[idx + len(marker):].strip()
        if rest.startswith((':', '：')):
            rest = rest[1:].strip()
        candidate = _strip_direct_answer(rest)
        if candidate and "\n" not in candidate and len(candidate) <= 120:
            return candidate
    return ""  # no match


def quality_check(response_text: str, complexity: float, backend: str,
                  query: str = "") -> bool:
    """检查回答质量，返回 False 表示需要重试。"""
    if not response_text:
        return False
    if response_text.startswith("[ERR]"):
        return False
    if http_caller._is_backend_error(response_text):
        return False
    expected = expected_direct_answer(query)
    if expected and response_text.strip() != expected:
        return False
    if (len(response_text) < 30 and complexity > 0.3
            and not allows_short_direct_answer(query, response_text)):
        return False
    uncertain_phrases = ["I cannot", "我无法", "抱歉，我不能"]
    if any(phrase in response_text for phrase in uncertain_phrases):
        if complexity < 0.5:
            return False
    return True


def honest_failure_response(chat_id: str, fmt: str = "openai",
                            request_model: str = None) -> dict:
    """所有后端都失败时的诚实回答。"""
    content = "当前所有服务暂时不可用，请稍后重试。如果问题持续，请联系管理员。"
    if fmt == "anthropic":
        return build_anthropic_response(
            chat_id, content, "fallback_exhausted", request_model or MODEL_ID)
    return build_response(chat_id, content, "fallback_exhausted", 0)


async def try_backend(
    backend_name: str,
    query: str,
    max_tokens: int = 1024,
    *,
    messages: list[dict] | None = None,
) -> dict | None:
    """尝试调用一个后端，失败返回 None。返回 smart_router.route() 兼容的 dict。"""
    if backend_name not in smart_router.BACKENDS:
        return None
    if not _backend_enabled.get(backend_name, True):
        return None
    if not smart_router.cb_allow(backend_name):
        return None
    try:
        msgs = messages if messages else [{"role": "user", "content": query}]
        result = await asyncio.wait_for(
            asyncio.to_thread(smart_router.call_api, backend_name, msgs, max_tokens),
            timeout=35.0
        )
        if result is None or (isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)):
            smart_router.cb_record(backend_name, False)
            return None
        return {"answer": result, "backend": backend_name, "total_ms": 0}
    except asyncio.TimeoutError:
        smart_router.cb_record(backend_name, False)
        return None
    except Exception as e:
        logging.debug(f"[TRY_BACKEND] {backend_name}: {type(e).__name__}: {e}")
        smart_router.cb_record(backend_name, False)
        return None
