"""Routing selector constants and static metadata."""

MAX_FALLBACKS = 12

# Static latency estimates (ms) for known fast backends
_STATIC_LATENCY_ESTIMATE = {
    "cerebras_llama8b": 800,
    "cerebras_gptoss": 1200,
    "cerebras_qwen235b": 1500,
    "groq_gptoss_20b": 900,
    "groq_gptoss": 1100,
    "groq_llama8b": 700,
    "groq_llama70b": 1200,
    "groq_llama4": 1000,
    "groq_qwen32b": 1100,
    "github_gpt4o_mini": 1000,
    "github_gpt4o": 1500,
    "mistral_small": 1000,
    "mistral_large": 1500,
    "longcat_chat": 3000,
    "longcat_lite": 2000,
    "scnet_qwen30b": 1200,
    "scnet_qwen235b": 2000,
    "scnet_ds_flash": 1000,
    "scnet_ds_pro": 2500,
}

STRONG_CODING_TOOL_BACKENDS = {
    "dashscope_coding",
    "github_gpt4o_code",
    "mistral_large_code",
    "or_gptoss_120b_code",
    "cfai_qwen_coder_code",
    "scnet_qwen235b_code",
    "scnet_ds_pro_code",
    "ms_qwen35_27b_code",
    "ms_kimi_k25_code",
    "ms_deepseek_v4_code",
    "ms_glm5_code",
}

_NATIVE_TOOL_PREFER = {"github", "chinamobile", "ddg", "groq", "cerebras", "longcat"}
