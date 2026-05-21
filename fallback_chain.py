"""fallback_chain.py — Fallback 降级链 + 质量检查
从 server.py 提取，管理后端失败后的同级降级和跨级升级。
"""
import pathlib

_BASE = pathlib.Path(__file__).parent

# ── 后端层级映射 ─────────────────────────────────────────────────────────────

BACKEND_TIERS = {
    "L1_free": ["longcat_lite", "longcat_chat", "longcat", "longcat_thinking", "longcat_omni"],
    "L2_nvidia": ["nvidia_qwen_coder", "nvidia_nemotron", "nvidia_llama70b"],
    "L3_paid": ["deepseek_flash", "deepseek_pro", "claude"],
}

FALLBACK_LOG = str(_BASE / "data" / "fallback_log.jsonl")


def get_same_tier_backends(current_backend: str) -> list[str]:
    """获取同层级的其他后端（排除当前的）。"""
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            return [b for b in backends if b != current_backend]
    return []


def get_upgrade_chain(current_backend: str) -> list[str]:
    """获取升级链：当前层级之上的所有后端。"""
    tiers = list(BACKEND_TIERS.keys())
    current_tier = None
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            current_tier = tier
            break
    if not current_tier:
        return ["longcat_chat"]
    tier_idx = tiers.index(current_tier)
    upgrade_backends = []
    for tier in tiers[tier_idx + 1:]:
        upgrade_backends.extend(BACKEND_TIERS[tier][:2])
    return upgrade_backends


def default_route(query: str, ide: str = "unknown") -> str:
    """当路由模型输出无效时，用简单规则选后端。"""
    query_lower = query.lower()
    if len(query) < 50:
        return "longcat_lite"
    code_keywords = ["代码", "code", "函数", "function", "bug", "error", "def ", "class "]
    if any(kw in query_lower for kw in code_keywords):
        return "nvidia_qwen_coder"
    if len(query) > 200:
        return "longcat"
    return "longcat_chat"


def quality_check(response_text: str, complexity: float, backend: str) -> bool:
    """检查回答质量，返回 False 表示需要重试。"""
    if not response_text:
        return False
    if len(response_text) < 30 and complexity > 0.3:
        return False
    if response_text.startswith("[ERR]") or "暂时不可用" in response_text:
        return False
    uncertain = ["I cannot", "我无法", "抱歉，我不能"]
    if any(phrase in response_text for phrase in uncertain):
        if complexity < 0.5:
            return False
    return True
