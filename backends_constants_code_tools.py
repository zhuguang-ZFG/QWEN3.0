"""Backend code/tool capability frozensets.

Split from backends_constants.py to keep individual files under 300 lines.
"""

CODE_CAPABLE_BACKENDS = frozenset(
    {
        "scnet_ds_flash",
        "scnet_qwen235b",
        "scnet_qwen30b",
        "scnet_ds_pro",
        "github_gpt4o",
        "github_gpt4o_mini",
        "github_codestral",
        "cf_qwen_coder",
        "cfai_qwen_coder",
        "or_qwen3_coder",
        "or_gptoss_120b",
        "cf_gptoss_120b",
        "cf_deepseek_r1",
        "cf_qwen3_30b",
        "cfai_deepseek_r1",
        "kilo_auto_free",
        "kilo_laguna_m1",
        "kilo_stepfun_flash",
        "mistral_large",
        "mistral_devstral",
        "mistral_pixtral",
        "mistral_codestral",
        "cerebras_gptoss",
        "groq_gptoss",
        "groq_gptoss_20b",
        "deepinfra_qwen235b",
        # ModelScope 魔搭
        "ms_qwen_coder_32b",
        "ms_qwen_coder_14b",
        "ms_qwen_coder_7b",
        # NVIDIA NIM 新增强力模型
        "nvidia_deepseek_v4",
        "nvidia_qwen35_coder",
        # FreeModel.dev
        "fm_gpt55",
        "fm_gpt54",
        "fm_gpt54_mini",
        "fm_gpt53_codex",
        # OpenGateway (Sionic AI)
        "ogw_gpt55",
        "ogw_gpt54",
        "ogw_gpt5_codex",
        "ogw_gpt4o_mini",
        "ogw_gpt54_mini",
        "ogw_claude_sonnet",
        "ogw_claude_haiku",
        "ogw_deepseek_v4",
        "ogw_deepseek_flash",
        "ogw_grok",
        "ogw_kimi",
        "ogw_glm5",
        "ogw_minimax",
        # Agnes AI (Sapiens AI, 新加坡免费网关)
        "agnes20",
        "agnes15",
        # ModelScope 扩展 (2026-06-06)
        "ms_ds_v32",
        "ms_ds_r1",
        "ms_qwen3_235b",
        "ms_qwen3_235b_think",
        "ms_qwen3_32b",
        "ms_qwen3_coder_30b",
        "ms_qwen3_next_80b",
        "ms_qwen3_next_80b_think",
        "ms_qwen35_35b",
        "ms_qwen35_122b",
        "ms_qwen35_397b",
        "ms_glm51",
        "ms_step37",
        "ms_mistral_large",
        "ms_llama4",
        "ms_interns2",
    }
)

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
