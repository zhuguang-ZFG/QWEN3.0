# coding capability retired v3.0，但本模块的后端能力矩阵（DIMENSIONS/默认矩阵/classify_intent）
# 仍被路由与测试使用，未退役。
"""
LiMa Capability Matrix — 后端能力矩阵 + 精细路由

基于评测结果，为每个后端标注 4 维能力分数。
路由时根据请求意图从能力矩阵中选择最匹配的后端。
"""

import json
import logging
import os

logger = logging.getLogger("capability_matrix")

# ── 能力维度 ─────────────────────────────────────────────────────────────────

DIMENSIONS = ["chinese", "english", "reasoning", "speed"]

# ── 默认能力矩阵（手动标注 + 评测结果覆盖）─────────────────────────────────

_DEFAULT_MATRIX = {
    # 代码专用后端
    "nvidia_qwen_coder": {"chinese": 7, "english": 7, "reasoning": 6, "speed": 6},
    "cf_qwen_coder": {"chinese": 7, "english": 7, "reasoning": 6, "speed": 7},
    "github_codestral": {"chinese": 3, "english": 8, "reasoning": 5, "speed": 8},
    "mistral_codestral": {"chinese": 3, "english": 8, "reasoning": 5, "speed": 7},
    "mistral_devstral": {"chinese": 3, "english": 8, "reasoning": 5, "speed": 7},
    "or_qwen3_coder": {"chinese": 7, "english": 7, "reasoning": 6, "speed": 5},
    # 快速通用后端
    "groq_llama70b": {"chinese": 4, "english": 8, "reasoning": 6, "speed": 9},
    "groq_qwen32b": {"chinese": 6, "english": 7, "reasoning": 6, "speed": 9},
    "groq_gptoss": {"chinese": 4, "english": 7, "reasoning": 5, "speed": 9},
    "groq_llama4": {"chinese": 5, "english": 8, "reasoning": 7, "speed": 9},
    "cerebras_gptoss": {"chinese": 4, "english": 7, "reasoning": 5, "speed": 9},
    # LongCat 系列
    "longcat_lite": {"chinese": 7, "english": 6, "reasoning": 4, "speed": 8},
    "longcat_chat": {"chinese": 8, "english": 7, "reasoning": 6, "speed": 7},
    "longcat": {"chinese": 9, "english": 8, "reasoning": 7, "speed": 6},
    "longcat_thinking": {"chinese": 9, "english": 8, "reasoning": 9, "speed": 4},
    "longcat_web": {"chinese": 8, "english": 7, "reasoning": 6, "speed": 5},
    "longcat_web_think": {"chinese": 9, "english": 8, "reasoning": 8, "speed": 3},
    "longcat_web_research": {"chinese": 9, "english": 8, "reasoning": 8, "speed": 2},
    # Cloudflare 系列
    "cf_llama70b": {"chinese": 4, "english": 8, "reasoning": 6, "speed": 7},
    "cf_kimi_k26": {"chinese": 9, "english": 7, "reasoning": 7, "speed": 3},
    "cf_qwen3_30b": {"chinese": 7, "english": 7, "reasoning": 6, "speed": 7},
    "cf_gemma4": {"chinese": 3, "english": 7, "reasoning": 5, "speed": 7},
    # 本地 Ollama (RTX 5060 Ti)
    "local_coder14b": {"chinese": 6, "english": 7, "reasoning": 6, "speed": 6},
    "local_reasoning": {"chinese": 5, "english": 6, "reasoning": 8, "speed": 4},
    "local_general": {"chinese": 5, "english": 7, "reasoning": 5, "speed": 6},
    "local_fast": {"chinese": 4, "english": 5, "reasoning": 3, "speed": 9},
    "local_chat": {"chinese": 3, "english": 4, "reasoning": 2, "speed": 10},
    # DuckDuckGo AI (免费)
    "ddg_gpt4o_mini": {"chinese": 7, "english": 9, "reasoning": 7, "speed": 7},
    "ddg_claude_haiku": {"chinese": 7, "english": 9, "reasoning": 7, "speed": 8},
    "ddg_llama4": {"chinese": 5, "english": 8, "reasoning": 7, "speed": 7},
    "ddg_o3_mini": {"chinese": 6, "english": 9, "reasoning": 9, "speed": 6},
    "ddg_mistral": {"chinese": 4, "english": 7, "reasoning": 5, "speed": 7},
    # lza6 CF Workers
    "tele_reason": {"chinese": 5, "english": 7, "reasoning": 8, "speed": 6},
    "tele_standard": {"chinese": 5, "english": 7, "reasoning": 5, "speed": 7},
    "tele_apps": {"chinese": 5, "english": 7, "reasoning": 5, "speed": 7},
    "assist_brainstorm": {"chinese": 5, "english": 7, "reasoning": 6, "speed": 6},
    "vision_joycaption": {"chinese": 3, "english": 6, "reasoning": 3, "speed": 5},
    # StockAI
    "stock_gpt4o_mini": {"chinese": 7, "english": 9, "reasoning": 7, "speed": 7},
    "stock_gemini_flash": {"chinese": 7, "english": 8, "reasoning": 7, "speed": 8},
    "stock_deepseek": {"chinese": 9, "english": 8, "reasoning": 8, "speed": 6},
    "stock_llama4": {"chinese": 5, "english": 8, "reasoning": 7, "speed": 7},
    "stock_kimi_k2": {"chinese": 9, "english": 7, "reasoning": 8, "speed": 6},
    "stock_glm46": {"chinese": 9, "english": 7, "reasoning": 6, "speed": 7},
    "stock_qwen3_coder": {"chinese": 7, "english": 7, "reasoning": 7, "speed": 6},
    "stock_news": {"chinese": 5, "english": 7, "reasoning": 4, "speed": 7},
    "stock_mistral": {"chinese": 4, "english": 7, "reasoning": 5, "speed": 7},
    # TheOldLLM
    "oldllm_gpt54": {"chinese": 8, "english": 10, "reasoning": 9, "speed": 5},
    "oldllm_gpt53": {"chinese": 8, "english": 10, "reasoning": 9, "speed": 5},
    "oldllm_gpt52": {"chinese": 8, "english": 10, "reasoning": 9, "speed": 5},
    "oldllm_gpt51": {"chinese": 8, "english": 10, "reasoning": 9, "speed": 5},
    "oldllm_gpt5": {"chinese": 8, "english": 10, "reasoning": 8, "speed": 5},
    "oldllm_gpt5_mini": {"chinese": 7, "english": 9, "reasoning": 7, "speed": 7},
    "oldllm_gpt41": {"chinese": 7, "english": 9, "reasoning": 8, "speed": 6},
    "oldllm_gpt41_mini": {"chinese": 7, "english": 9, "reasoning": 7, "speed": 7},
    "oldllm_gpt41_nano": {"chinese": 5, "english": 8, "reasoning": 5, "speed": 9},
    "oldllm_gpt4": {"chinese": 7, "english": 9, "reasoning": 8, "speed": 5},
    "oldllm_o1": {"chinese": 7, "english": 9, "reasoning": 10, "speed": 3},
    "oldllm_o4_mini": {"chinese": 7, "english": 9, "reasoning": 9, "speed": 6},
    # 国家超算互联网平台 (scnet.cn)
    "scnet_qwen30b": {"chinese": 9, "english": 7, "reasoning": 7, "speed": 8},
    "scnet_minimax": {"chinese": 8, "english": 7, "reasoning": 7, "speed": 5},
    "scnet_qwen235b": {"chinese": 9, "english": 8, "reasoning": 8, "speed": 7},
    "scnet_ds_flash": {"chinese": 9, "english": 8, "reasoning": 8, "speed": 8},
    "scnet_ds_pro": {"chinese": 9, "english": 9, "reasoning": 9, "speed": 5},
    # Kimi (月之暗面, K2.6)
    "kimi": {"chinese": 10, "english": 7, "reasoning": 7, "speed": 7},
    "kimi_thinking": {"chinese": 10, "english": 8, "reasoning": 9, "speed": 5},
    "kimi_search": {"chinese": 10, "english": 7, "reasoning": 7, "speed": 4},
}

# ── 加载评测结果覆盖 ─────────────────────────────────────────────────────────

_EVAL_FILE = os.path.join(os.path.dirname(__file__), "data", "backend_eval_results.json")
_matrix: dict[str, dict[str, int]] = {}


def _load_matrix():
    """加载能力矩阵：先用默认值，再用评测结果覆盖。"""
    global _matrix
    _matrix = dict(_DEFAULT_MATRIX)

    if os.path.exists(_EVAL_FILE):
        try:
            with open(_EVAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, scores in data.get("results", {}).items():
                if scores.get("available") and scores.get("total", 0) > 15:
                    _matrix[name] = {d: scores.get(d, 0) for d in DIMENSIONS}
            logger.info(f"[CAP] Loaded {len(_matrix)} backends from eval results")
        except Exception as e:
            logger.warning(f"[CAP] Failed to load eval: {e}")


_load_matrix()


# ── 意图分类 ─────────────────────────────────────────────────────────────────

_CHINESE_SIGNALS = ["中文", "chinese", "翻译", "解释一下", "什么是", "怎么"]
_REASONING_SIGNALS = ["计算", "推理", "数学", "逻辑", "证明", "分析", "calculate", "math", "prove", "logic", "reason"]


def classify_intent(query: str, messages: list[dict] = None) -> str:
    """
    精细意图分类: chinese | reasoning | english | simple
    """
    messages = messages or []
    q = query.lower()
    total_ctx = sum(len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str))

    cn_chars = sum(1 for c in query if "一" <= c <= "鿿")
    if cn_chars > len(query) * 0.3 or any(kw in q for kw in _CHINESE_SIGNALS):
        return "chinese"

    if any(kw in q for kw in _REASONING_SIGNALS):
        return "reasoning"

    if total_ctx > 3000 or len(query) > 500 or len(messages) > 8:
        return "reasoning"

    return "english"


def select_backends(intent: str, top_n: int = 8) -> list[str]:
    """根据意图从能力矩阵中选 top-N 后端（按该维度分数排序）。"""
    dim = _intent_to_dimension(intent)

    scored = []
    for name, caps in _matrix.items():
        primary = caps.get(dim, 0)
        speed = caps.get("speed", 5)
        score = primary * 2 + speed
        scored.append((name, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored[:top_n]]


def _intent_to_dimension(intent: str) -> str:
    """意图映射到能力维度。"""
    mapping = {
        "chinese": "chinese",
        "reasoning": "reasoning",
        "english": "english",
        "simple": "speed",
    }
    return mapping.get(intent, "english")


def get_backend_capability(backend: str) -> dict[str, int]:
    """获取单个后端的能力分数。"""
    return _matrix.get(backend, {d: 5 for d in DIMENSIONS})


def reload():
    """重新加载评测结果（供 admin 接口调用）。"""
    _load_matrix()
