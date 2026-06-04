"""
LiMa Capability Matrix — 后端能力矩阵 + 精细路由

基于评测结果，为每个后端标注 6 维能力分数。
路由时根据请求意图从能力矩阵中选择最匹配的后端。
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger("capability_matrix")

# ── 能力维度 ─────────────────────────────────────────────────────────────────

DIMENSIONS = ["code", "debug", "chinese", "english", "reasoning", "speed", "tool_calls"]

# ── 默认能力矩阵（手动标注 + 评测结果覆盖）─────────────────────────────────

_DEFAULT_MATRIX = {
    # 代码专用后端
    "nvidia_qwen_coder": {"code": 9, "debug": 8, "chinese": 7, "english": 7, "reasoning": 6, "speed": 6, "tool_calls": 0},
    "cf_qwen_coder": {"code": 9, "debug": 8, "chinese": 7, "english": 7, "reasoning": 6, "speed": 7, "tool_calls": 5},
    "github_codestral": {"code": 9, "debug": 8, "chinese": 3, "english": 8, "reasoning": 5, "speed": 8, "tool_calls": 8},
    "mistral_codestral": {"code": 9, "debug": 8, "chinese": 3, "english": 8, "reasoning": 5, "speed": 7, "tool_calls": 8},
    "mistral_devstral": {"code": 8, "debug": 7, "chinese": 3, "english": 8, "reasoning": 5, "speed": 7, "tool_calls": 8},
    "or_qwen3_coder": {"code": 9, "debug": 8, "chinese": 7, "english": 7, "reasoning": 6, "speed": 5, "tool_calls": 0},
    "opencode_stealth": {"code": 8, "debug": 7, "chinese": 5, "english": 7, "reasoning": 6, "speed": 6, "tool_calls": 0},

    # 快速通用后端
    "groq_llama70b": {"code": 7, "debug": 6, "chinese": 4, "english": 8, "reasoning": 6, "speed": 9, "tool_calls": 8},
    "groq_qwen32b": {"code": 7, "debug": 6, "chinese": 6, "english": 7, "reasoning": 6, "speed": 9, "tool_calls": 8},
    "groq_gptoss": {"code": 6, "debug": 5, "chinese": 4, "english": 7, "reasoning": 5, "speed": 9, "tool_calls": 8},
    "groq_llama4": {"code": 7, "debug": 6, "chinese": 5, "english": 8, "reasoning": 7, "speed": 9, "tool_calls": 8},
    "cerebras_gptoss": {"code": 6, "debug": 5, "chinese": 4, "english": 7, "reasoning": 5, "speed": 9, "tool_calls": 0},

    # LongCat 系列
    "longcat_lite": {"code": 5, "debug": 4, "chinese": 7, "english": 6, "reasoning": 4, "speed": 8, "tool_calls": 8},
    "longcat_chat": {"code": 7, "debug": 6, "chinese": 8, "english": 7, "reasoning": 6, "speed": 7, "tool_calls": 0},
    "longcat": {"code": 8, "debug": 7, "chinese": 9, "english": 8, "reasoning": 7, "speed": 6, "tool_calls": 9},
    "longcat_thinking": {"code": 9, "debug": 8, "chinese": 9, "english": 8, "reasoning": 9, "speed": 4, "tool_calls": 0},
    "longcat_web": {"code": 7, "debug": 6, "chinese": 8, "english": 7, "reasoning": 6, "speed": 5, "tool_calls": 5},
    "longcat_web_think": {"code": 8, "debug": 7, "chinese": 9, "english": 8, "reasoning": 8, "speed": 3, "tool_calls": 5},
    "longcat_web_research": {"code": 7, "debug": 6, "chinese": 9, "english": 8, "reasoning": 8, "speed": 2, "tool_calls": 0},

    # Cloudflare 系列
    "cf_llama70b": {"code": 7, "debug": 6, "chinese": 4, "english": 8, "reasoning": 6, "speed": 7, "tool_calls": 0},
    "cf_kimi_k26": {"code": 8, "debug": 7, "chinese": 9, "english": 7, "reasoning": 7, "speed": 3, "tool_calls": 0},
    "cf_qwen3_30b": {"code": 7, "debug": 6, "chinese": 7, "english": 7, "reasoning": 6, "speed": 7, "tool_calls": 0},
    "cf_gemma4": {"code": 6, "debug": 5, "chinese": 3, "english": 7, "reasoning": 5, "speed": 7, "tool_calls": 0},

    # 本地 Ollama (RTX 5060 Ti)
    # M1: local_* Ollama models deleted

    # DuckDuckGo AI (免费)
    # M6: ddg_* backends deleted

    # lza6 CF Workers
    "tele_reason": {"code": 6, "debug": 6, "chinese": 5, "english": 7, "reasoning": 8, "speed": 6, "tool_calls": 0},
    "tele_standard": {"code": 6, "debug": 5, "chinese": 5, "english": 7, "reasoning": 5, "speed": 7, "tool_calls": 0},
    "tele_apps": {"code": 7, "debug": 6, "chinese": 5, "english": 7, "reasoning": 5, "speed": 7, "tool_calls": 0},
    "assist_brainstorm": {"code": 5, "debug": 4, "chinese": 5, "english": 7, "reasoning": 6, "speed": 6, "tool_calls": 0},
    "vision_joycaption": {"code": 2, "debug": 2, "chinese": 3, "english": 6, "reasoning": 3, "speed": 5, "tool_calls": 0},

    # StockAI
    "stock_gpt4o_mini": {"code": 8, "debug": 7, "chinese": 7, "english": 9, "reasoning": 7, "speed": 7, "tool_calls": 0},
    "stock_gemini_flash": {"code": 8, "debug": 7, "chinese": 7, "english": 8, "reasoning": 7, "speed": 8, "tool_calls": 0},
    "stock_deepseek": {"code": 9, "debug": 8, "chinese": 9, "english": 8, "reasoning": 8, "speed": 6, "tool_calls": 0},
    "stock_llama4": {"code": 7, "debug": 6, "chinese": 5, "english": 8, "reasoning": 7, "speed": 7, "tool_calls": 0},
    "stock_kimi_k2": {"code": 8, "debug": 7, "chinese": 9, "english": 7, "reasoning": 8, "speed": 6, "tool_calls": 0},
    "stock_glm46": {"code": 7, "debug": 6, "chinese": 9, "english": 7, "reasoning": 6, "speed": 7, "tool_calls": 0},
    "stock_qwen3_coder": {"code": 9, "debug": 8, "chinese": 7, "english": 7, "reasoning": 7, "speed": 6, "tool_calls": 0},
    "stock_news": {"code": 3, "debug": 2, "chinese": 5, "english": 7, "reasoning": 4, "speed": 7, "tool_calls": 0},
    "stock_mistral": {"code": 6, "debug": 5, "chinese": 4, "english": 7, "reasoning": 5, "speed": 7, "tool_calls": 0},

    # TheOldLLM
    "oldllm_gpt54": {"code": 10, "debug": 9, "chinese": 8, "english": 10, "reasoning": 9, "speed": 5, "tool_calls": 8},
    "oldllm_gpt53": {"code": 10, "debug": 9, "chinese": 8, "english": 10, "reasoning": 9, "speed": 5, "tool_calls": 8},
    "oldllm_gpt52": {"code": 10, "debug": 9, "chinese": 8, "english": 10, "reasoning": 9, "speed": 5, "tool_calls": 8},
    "oldllm_gpt51": {"code": 9, "debug": 9, "chinese": 8, "english": 10, "reasoning": 9, "speed": 5, "tool_calls": 8},
    "oldllm_gpt5": {"code": 9, "debug": 8, "chinese": 8, "english": 10, "reasoning": 8, "speed": 5, "tool_calls": 8},
    "oldllm_gpt5_mini": {"code": 8, "debug": 7, "chinese": 7, "english": 9, "reasoning": 7, "speed": 7, "tool_calls": 8},
    "oldllm_gpt41": {"code": 9, "debug": 8, "chinese": 7, "english": 9, "reasoning": 8, "speed": 6, "tool_calls": 0},
    "oldllm_gpt41_mini": {"code": 8, "debug": 7, "chinese": 7, "english": 9, "reasoning": 7, "speed": 7, "tool_calls": 0},
    "oldllm_gpt41_nano": {"code": 6, "debug": 5, "chinese": 5, "english": 8, "reasoning": 5, "speed": 9, "tool_calls": 0},
    "oldllm_gpt4": {"code": 8, "debug": 8, "chinese": 7, "english": 9, "reasoning": 8, "speed": 5, "tool_calls": 0},
    "oldllm_o1": {"code": 9, "debug": 9, "chinese": 7, "english": 9, "reasoning": 10, "speed": 3, "tool_calls": 0},
    "oldllm_o4_mini": {"code": 9, "debug": 8, "chinese": 7, "english": 9, "reasoning": 9, "speed": 6, "tool_calls": 0},

    # 国家超算互联网平台 (scnet.cn)
    "scnet_qwen30b": {"code": 8, "debug": 7, "chinese": 9, "english": 7, "reasoning": 7, "speed": 8, "tool_calls": 5},
    "scnet_minimax": {"code": 7, "debug": 6, "chinese": 8, "english": 7, "reasoning": 7, "speed": 5, "tool_calls": 0},
    "scnet_qwen235b": {"code": 9, "debug": 8, "chinese": 9, "english": 8, "reasoning": 8, "speed": 7, "tool_calls": 5},
    "scnet_ds_flash": {"code": 9, "debug": 8, "chinese": 9, "english": 8, "reasoning": 8, "speed": 8, "tool_calls": 5},
    "scnet_ds_pro": {"code": 10, "debug": 9, "chinese": 9, "english": 9, "reasoning": 9, "speed": 5, "tool_calls": 5},

    # Kimi (月之暗面, K2.6)
    "kimi": {"code": 8, "debug": 7, "chinese": 10, "english": 7, "reasoning": 7, "speed": 7, "tool_calls": 5},
    "kimi_thinking": {"code": 9, "debug": 8, "chinese": 10, "english": 8, "reasoning": 9, "speed": 5, "tool_calls": 5},
    "kimi_search": {"code": 7, "debug": 6, "chinese": 10, "english": 7, "reasoning": 7, "speed": 4, "tool_calls": 0},

    # ModelScope 魔搭 (Qwen2.5-Coder 系列)
    "ms_qwen_coder_32b": {"code": 9, "debug": 8, "chinese": 8, "english": 7, "reasoning": 7, "speed": 6, "tool_calls": 0},
    "ms_qwen_coder_14b": {"code": 8, "debug": 7, "chinese": 8, "english": 7, "reasoning": 6, "speed": 7, "tool_calls": 0},
    "ms_qwen_coder_7b": {"code": 7, "debug": 6, "chinese": 8, "english": 7, "reasoning": 5, "speed": 8, "tool_calls": 0},
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

_CODE_SIGNALS = [
    "代码", "code", "函数", "function", "bug", "error", "fix",
    "def ", "class ", "import ", "```", "compile", "debug",
    "实现", "implement", "refactor", "重构",
    "TypeError", "ValueError", "Exception", "traceback",
]
_CHINESE_SIGNALS = ["中文", "chinese", "翻译", "解释一下", "什么是", "怎么"]
_REASONING_SIGNALS = ["计算", "推理", "数学", "逻辑", "证明", "分析",
                      "calculate", "math", "prove", "logic", "reason"]


def classify_intent(query: str, messages: list[dict] = None) -> str:
    """
    精细意图分类: code | chinese | reasoning | english | simple
    """
    messages = messages or []
    q = query.lower()
    total_ctx = sum(len(m.get("content", "")) for m in messages
                    if isinstance(m.get("content"), str))

    if any(kw in q for kw in _CODE_SIGNALS):
        return "code"

    cn_chars = sum(1 for c in query if '一' <= c <= '鿿')
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
        "code": "code",
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
