"""Backend capability sets and routing constants."""

from brand_config import PUBLIC_MODEL_NAME
from backends_constants_code_tools import (
    CODE_CAPABLE_BACKENDS,
    TOOL_CAPABLE_BACKENDS,
)


# Thinking-capable backends in priority order
THINKING_BACKENDS = [
    "scnet_ds_pro",  # 支持深度推理（优先，本地可用）
    "scnet_ds_flash",  # 备用
    "kimi_thinking",  # Kimi 思考模式
    "or_deepseek_r1",  # DeepSeek R1（需要 OpenRouter key）
]

# Vision-capable backends (must be registered in BACKENDS)
VISION_BACKENDS = [
    "cf_vision",
    "google_flash",
    "google_flash_lite",
    "github_gpt4o",
    "mistral_pixtral",
    "cohere_vision",
    "or_deepseek_r1",
    "vision_joycaption",
]

# Backends that should use the configured outbound proxy.
GFW_BACKENDS = frozenset(
    {
        "google_flash",
        "google_flash_lite",
        "google_pro",
        "mistral_large",
        "mistral_small",
        "mistral_medium",
        "mistral_codestral",
        "mistral_devstral",
        "mistral_pixtral",
        "groq_llama70b",
        "groq_gptoss",
        "groq_gptoss_20b",
        "groq_qwen32b",
        "groq_llama4",
        "groq_llama8b",
        "cerebras_qwen235b",
        "cerebras_llama8b",
        "cerebras_gptoss",
        "or_deepseek_r1",
        "or_qwen3_coder",
        "or_llama70b",
        "or_nemotron",
        "or_qwen3_80b",
        "or_nemotron120b",
        "or_gptoss_120b",
        "or_glm45",
        "or_minimax",
        "or_gemma4",
        "or_llama4_scout",
        "kilo_auto_free",
        "kilo_laguna_m1",
        "kilo_stepfun_flash",
        "github_gpt4o",
        "github_gpt4o_mini",
        "github_gpt5",
        "github_o3_mini",
        "github_o4_mini",
        "github_deepseek_r1",
        "github_llama70b",
        "github_codestral",
        "naga_llama70b",
        "naga_gpt41mini",
        "naga_glm45",
        "naga_llama4",
        "featherless",
        "glhf",
        "agentrouter",
        "zuki_codestral",
        "zuki_mistral_small",
        "fireworks_llama405b",
        "cohere_command",
        "cohere_command_plus",
        "cohere_reasoning",
        "cohere_vision",
        "sambanova_llama4",
        "sambanova_ds_v3",
        "deepinfra_llama4",
        "deepinfra_qwen235b",
        "ovh_llama70b",
        "ovh_deepseek",
        "ogw_gpt55",
        "ogw_gpt54",
        "ogw_gpt5_codex",
        "ogw_gpt4o_mini",
        "ogw_claude_sonnet",
        "ogw_claude_haiku",
        "ogw_deepseek_v4",
        "ogw_deepseek_flash",
        "ogw_grok",
        "ogw_kimi",
        "ogw_glm5",
        "ogw_minimax",
    }
)

WEAK_BACKENDS = frozenset({"chat_ubi", "pollinations", "llm7"})

# Models capable of tool calls and directory-mode skill injection
STRONG_MODELS = frozenset(
    {
        "longcat",
        "naga_gpt41mini",
        "or_deepseek_r1",
        "nvidia_qwen_coder",
        "fireworks_llama405b",
        "deepinfra_llama4",
        "hermes_agent",
    }
)

KEY_POOL_PREFIXES = {
    "groq_": "groq",
    "or_": "openrouter",
    "github_": "github",
    "mistral_": "mistral",
    "cerebras_": "cerebras",
    "google_": "google",
    "cf_": "cloudflare",
    "nvidia_": "nvidia",
    "zhipu_": "zhipu",
    "silicon_": "siliconflow",
    "baidu_": "baidu",
    "volcengine_": "volcengine",
    "aliyun_": "aliyun",
    "tencent_": "tencent",
    "naga_": "naga",
    "zuki_": "zuki",
    "cohere_": "cohere",
    "sambanova_": "sambanova",
    "deepinfra_": "deepinfra",
    "fireworks_": "fireworks",
    "ms_": "modelscope",
    "fm_": "freemodel",
    "ogw_": "opengateway",
    "agnes": "agnes_ai",
}

VISION_SYSTEM_PROMPT = "你是一位耐心的老师。用户上传了一道题目的图片。请：1. 识别题目内容 2. 分步骤解答 3. 给出最终答案。如果是选择题，明确指出正确选项。"

# Known IDE sources used by routing_engine.classify() and router_v3.classify_request().
_IDE_FINGERPRINTS = {
    "cursor": ["intelligent programmer", "You are Cursor"],
    "claude_code": ["CLAUDE.md", "Claude Code", "EnterPlanMode"],
    "codex": ["Codex", "codex"],
    "aider": ["SEARCH/REPLACE", "RepoMap"],
    "cline": ["<environment_details>", "Cline"],
    "continue": ["Continue is an open-source", "continue.dev"],
    "kiro": ["Kiro", "kiro"],
    "zed": ["Zed", "zed-editor", "You are an AI assistant in Zed"],
    "trae": ["Trae", "trae"],
    "windsurf": ["Windsurf", "Codeium"],
    "copilot": ["GitHub Copilot", "Copilot"],
}
IDE_SOURCES = list(_IDE_FINGERPRINTS.keys())

# ── Model Aliases: client-friendly names → LiMa backend names ──
# Used by model_resolver.resolve_backend() to let IDE clients
# (Cursor, Copilot, etc.) target specific LiMa backends.
MODEL_ALIASES = {
    # OpenAI
    "gpt-4o": "github_gpt4o",
    "gpt-4o-mini": "github_gpt4o_mini",
    "gpt-5": "github_gpt5",
    "o3-mini": "github_o3_mini",
    "o4-mini": "github_o4_mini",
    # DeepSeek
    "deepseek-v3": "scnet_ds_pro",
    "deepseek-v4": "scnet_ds_pro",
    "deepseek-v4-flash": "scnet_ds_flash",
    "deepseek-r1": "github_deepseek_r1",
    # Qwen
    "qwen-max": "scnet_qwen235b",
    "qwen-plus": "scnet_qwen30b",
    "qwen3-coder": "or_qwen3_coder",
    "qwen3-235b": "scnet_qwen235b",
    "qwen3-30b": "scnet_qwen30b",
    # Claude / Anthropic (via longcat proxy)
    "claude-opus": "longcat",
    "claude-sonnet": "longcat",
    "claude-haiku": "longcat",
    "claude-3-opus": "longcat",
    "claude-3-sonnet": "longcat",
    "claude-3-haiku": "longcat",
    # Llama
    "llama-3.3-70b": "groq_llama70b",
    "llama-3.1-8b": "groq_llama8b",
    "llama-4-scout": "groq_llama4",
    # Google
    "gemini-2.5-flash": "google_flash",
    "gemini-2.5-pro": "google_pro",
    "gemini-flash": "google_flash",
    # Mistral
    "mistral-large": "mistral_large",
    "mistral-small": "mistral_small",
    "codestral": "mistral_codestral",
    # MiMo
    "mimo": "mimo_web",
    "mimo-pro": "mimo_v2_pro",
    "mimo-v2.5-pro": "mimo_v2_5_pro",
    # FreeModel.dev
    "gpt-5.5": "fm_gpt55",
    "gpt-5.4": "fm_gpt54",
    "gpt-5.4-mini": "fm_gpt54_mini",
    "gpt-5.3-codex": "fm_gpt53_codex",
    # Kimi
    "kimi": "kimi",
    "kimi-k2.6": "kimi",
    # Cloudflare
    "gpt-oss-120b": "cf_gptoss_120b",
    # Fallback aliases (point to strong free backends)
    "default": None,
    "auto": None,
}
