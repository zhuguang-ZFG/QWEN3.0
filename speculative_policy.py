"""Speculative execution policy: complexity classification and backend affinity."""

from __future__ import annotations

import random

AFFINITY = {
    "simple_fast": [
        "longcat_lite",
        "longcat_chat",
        "google_flash",
        "groq_llama70b",
        "cerebras_gptoss",
        "cf_llama70b",
        "cf_qwen3_30b",
        "cf_gemma4",
        "ovh_llama70b",
        "groq_qwen32b",
        "nvidia_nemotron",
        "nvidia_llama70b",
        "sambanova_llama4",
        "deepinfra_llama4",
        "groq_llama4",
        "groq_gptoss",
        "google_flash_lite",
        "google_gemma4",
        "github_gpt4o_mini",
    ],
    "code": [
        "nvidia_qwen_coder",
        "cf_qwen_coder",
        "mistral_devstral",
        "groq_llama70b",
        "cerebras_gptoss",
        "github_codestral",
        "or_qwen3_coder",
        "mistral_codestral",
        "scnet_qwen30b",
        "scnet_qwen235b",
        "scnet_ds_flash",
    ],
    "complex_premium": [
        "longcat",
        "longcat_thinking",
        "fireworks_llama405b",
        "cf_kimi_k26",
        "mistral_large",
        "nvidia_qwen_coder",
    ],
}

_CODE_SIGNALS = [
    "代码",
    "code",
    "函数",
    "function",
    "bug",
    "error",
    "fix",
    "def ",
    "class ",
    "import ",
    "```",
    "compile",
    "debug",
    "实现",
    "implement",
    "refactor",
    "重构",
    "优化",
    "TypeError",
    "ValueError",
    "Exception",
    "traceback",
    "写",
    "改",
    "修复",
    "报错",
    "崩溃",
    "编译",
    "接口",
    "接口文档",
    "单元测试",
    "部署",
    "配置",
    "算法",
    "数据库",
    "查询",
    "性能",
    "内存",
    "多线程",
    "并发",
    "异步",
    "协程",
    "回调",
    "正则",
    "序列化",
    "反序列化",
    "编码",
    "解码",
]

_CODE_INDICATORS = ["```", "def ", "class ", "function ", "import ", "const "]
_FILE_EXTENSIONS = [".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp"]
_COMPLEX_KEYWORDS = [
    "refactor",
    "architecture",
    "migrate",
    "redesign",
    "concurrent",
    "distributed",
    "optimize",
    "performance",
]


def _has_code_signals(query: str) -> bool:
    """Check if query contains code-related keywords."""
    return any(kw in query for kw in _CODE_SIGNALS)


def _extract_user_text(messages: list[dict]) -> str:
    """Extract all user text from messages."""
    parts = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
    return " ".join(parts)


def score_request(messages: list[dict], ide: str = "") -> tuple[int, dict[str, str]]:
    """Unified request complexity scoring.

    Returns a score (1-10) and a dict of detected factor labels.
    This is the single source of truth used by both the speculative
    execution path and the legacy ComplexityAssessment facade.
    """
    user_text = _extract_user_text(messages)
    factors: dict[str, str] = {}
    score = 0

    char_count = len(user_text)
    if char_count >= 4000:
        factors["long_input"] = str(char_count)
        score += 3
    elif char_count >= 1500:
        factors["medium_input"] = str(char_count)
        score += 1

    code_hits = sum(1 for ind in _CODE_INDICATORS if ind in user_text)
    if code_hits >= 3:
        factors["heavy_code"] = str(code_hits)
        score += 2
    elif code_hits >= 1:
        factors["has_code"] = str(code_hits)
        score += 1

    file_hits = sum(1 for ext in _FILE_EXTENSIONS if ext in user_text)
    if file_hits >= 3:
        factors["multi_file"] = str(file_hits)
        score += 2
    elif file_hits >= 1:
        factors["single_file"] = str(file_hits)
        score += 1

    lowered = user_text.lower()
    kw_hits = sum(1 for kw in _COMPLEX_KEYWORDS if kw in lowered)
    if kw_hits >= 2:
        factors["complex_task"] = str(kw_hits)
        score += 2
    elif kw_hits >= 1:
        factors["moderate_task"] = str(kw_hits)
        score += 1

    if ide:
        score += 1
        factors["ide_present"] = ide

    return min(score, 10), factors


def classify_complexity(query: str, messages: list[dict]) -> str:
    """Return 'simple' | 'code' | 'complex' for routing strategy selection."""
    if _has_code_signals(query.lower()):
        return "code"
    score, _ = score_request(messages)
    if score >= 5:
        return "complex"
    return "simple"


def get_affinity_backends(complexity: str) -> list[str]:
    """Return shuffled backend pool for the given complexity tier."""
    try:
        import capability_matrix

        intent = {
            "simple": "english",
            "code": "code",
            "complex": "reasoning",
        }.get(complexity, "english")
        pool = capability_matrix.select_backends(intent, top_n=12)
    except Exception:
        if complexity == "simple":
            pool = list(AFFINITY["simple_fast"])
        elif complexity == "code":
            pool = list(AFFINITY["code"])
        else:
            pool = list(AFFINITY["complex_premium"])
    random.shuffle(pool)
    return pool
