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


def classify_complexity(query: str, messages: list[dict]) -> str:
    """Return 'simple' | 'code' | 'complex' for routing strategy selection."""
    query_len = len(query)
    total_context = sum(
        len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str)
    )

    code_signals = [
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
    query_lower = query.lower()
    if any(kw in query_lower for kw in code_signals):
        return "code"

    if total_context > 3000 or query_len > 500:
        return "complex"

    if len(messages) > 8:
        return "complex"

    if query_len < 80 and total_context < 500:
        return "simple"

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
