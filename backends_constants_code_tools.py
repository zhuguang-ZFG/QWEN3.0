# DEPRECATED v3.0 — coding capability retired
"""Backend tool capability frozensets.

Split from backends_constants.py to keep individual files under 300 lines.
"""

# Backends that reliably support tool_calls (OpenAI function calling format)
TOOL_CAPABLE_BACKENDS = frozenset(
    {
        # Groq backends with tool_calls capability
        "groq_llama70b",
        "groq_gptoss",
        "groq_qwen32b",
        "groq_llama4",
        # GitHub Models
        "github_gpt4o",
        "github_gpt4o_mini",
        "github_gpt5",
        "github_o3_mini",
        "github_o4_mini",
        # Cerebras
        "cerebras_qwen235b",
        # OpenRouter
        "or_gptoss_120b",
        "kilo_auto_free",
        "kilo_laguna_m1",
        "kilo_stepfun_flash",
        # NVIDIA
        "nvidia_mistral",
        "nvidia_deepseek_v4",
        "nvidia_qwen35_coder",
        "nvidia_kimi_k25",
        # FreeModel.dev
        "fm_gpt55",
        "fm_gpt54",
        "fm_gpt53_codex",
        # OpenGateway
        "ogw_gpt55",
        "ogw_gpt54",
        "ogw_gpt54_mini",
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
        # Agnes AI
        "agnes20",
        "agnes15",
        # Hermes Agent
        "hermes_agent",
        # ModelScope (existing)
        "ms_deepseek_v4",
        "ms_qwen35_27b",
        "ms_kimi_k25",
        "ms_glm5",
        # ModelScope 扩展 (2026-06-06)
        "ms_ds_v32",
        "ms_qwen3_235b",
        "ms_qwen3_coder_30b",
        "ms_qwen3_next_80b",
        "ms_qwen35_122b",
        "ms_glm51",
        "ms_step37",
        # China Mobile
        "chinamobile",
        # Longcat (Anthropic format, but supports tool_calls)
        "longcat",
        "longcat_openai",
    }
)
