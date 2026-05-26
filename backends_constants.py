"""Backend capability sets and routing constants."""
import os

PUBLIC_MODEL_NAME = os.environ.get('PUBLIC_MODEL_NAME', 'LiMa')

# Thinking-capable backends in priority order
THINKING_BACKENDS = ["or_deepseek_r1", "longcat_thinking", "longcat_web_think"]

# Vision-capable backends (must be registered in BACKENDS)
VISION_BACKENDS = [
    "longcat_omni",
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
GFW_BACKENDS = frozenset({
    'google_flash', 'google_flash_lite', 'google_gemini3', 'google_gemma4',
    'mistral_large', 'mistral_small', 'mistral_medium',
    'mistral_codestral', 'mistral_devstral', 'mistral_pixtral',
    'groq_llama70b', 'groq_gptoss', 'groq_gptoss_20b',
    'groq_qwen32b', 'groq_llama4', 'groq_llama8b',
    'cerebras_qwen235b', 'cerebras_llama8b', 'cerebras_gptoss',
    'or_deepseek_r1', 'or_qwen3_coder', 'or_llama70b', 'or_nemotron',
    'or_qwen3_80b', 'or_nemotron120b', 'or_gptoss_120b', 'or_glm45',
    'or_minimax', 'or_gemma4',
    'github_gpt4o', 'github_gpt4o_mini', 'github_gpt5', 'github_o3_mini',
    'github_o4_mini', 'github_deepseek_r1', 'github_llama70b', 'github_codestral',
    'naga_llama70b', 'naga_gpt41mini', 'naga_glm45', 'naga_llama4',
    'featherless', 'glhf', 'agentrouter',
    'zuki_codestral', 'zuki_mistral_small',
    'opencode_stealth', 'opencode_ds_flash', 'opencode_qwen',
    'opencode_nemotron', 'opencode_minimax',
    'fireworks_llama405b',
    'cohere_command', 'cohere_command_plus', 'cohere_reasoning', 'cohere_vision',
    'sambanova_llama4', 'sambanova_ds_v3',
    'deepinfra_llama4', 'deepinfra_qwen235b',
    'ovh_llama70b', 'ovh_deepseek',
})

WEAK_BACKENDS = frozenset({'chat_ubi', 'pollinations', 'llm7'})

# Models capable of tool calls and directory-mode skill injection
STRONG_MODELS = frozenset({
    "longcat_chat", "longcat_thinking", "longcat",
    "naga_gpt41mini",
    "or_deepseek_r1", "nvidia_qwen_coder",
    "opencode_stealth", "fireworks_llama405b", "deepinfra_llama4", "deepseek_free",
})

KEY_POOL_PREFIXES = {
    'groq_': 'groq',
    'or_': 'openrouter',
    'github_': 'github',
    'mistral_': 'mistral',
    'cerebras_': 'cerebras',
    'google_': 'google',
    'cf_': 'cloudflare',
    'nvidia_': 'nvidia',
    'zhipu_': 'zhipu',
    'silicon_': 'siliconflow',
    'baidu_': 'baidu',
    'volcengine_': 'volcengine',
    'aliyun_': 'aliyun',
    'tencent_': 'tencent',
    'naga_': 'naga',
    'zuki_': 'zuki',
    'cohere_': 'cohere',
    'sambanova_': 'sambanova',
    'deepinfra_': 'deepinfra',
    'fireworks_': 'fireworks',
}

CODE_CAPABLE_BACKENDS = frozenset({
    'scnet_ds_flash', 'scnet_qwen235b', 'scnet_qwen30b', 'scnet_ds_pro',
    'scnet_large_ds_flash', 'scnet_large_ds_pro',
    'github_gpt4o', 'github_gpt4o_mini', 'github_codestral',
    'cf_qwen_coder', 'cfai_qwen_coder', 'or_qwen3_coder', 'or_gptoss_120b',
    'cf_gptoss_120b', 'cf_deepseek_r1', 'cf_qwen3_30b', 'cfai_deepseek_r1',
    'mistral_large', 'mistral_devstral', 'mistral_pixtral', 'mistral_codestral',
    'cerebras_gptoss', 'groq_gptoss', 'groq_gptoss_20b',
    'deepinfra_qwen235b', 'local_coder14b',
})
VISION_SYSTEM_PROMPT = "你是一位耐心的老师。用户上传了一道题目的图片。请：1. 识别题目内容 2. 分步骤解答 3. 给出最终答案。如果是选择题，明确指出正确选项。"

# Known IDE sources (both canonical and lowercased forms for flexible matching).
# Used by routing_engine.classify() and router_v3.classify_request().
IDE_SOURCES = {"Claude Code", "claude_code", "Cursor", "cursor",
               "Codex", "codex", "Aider", "aider", "Cline", "cline",
               "Continue", "continue", "VS Code", "vscode", "vs code",
               "Kiro", "kiro", "Zed", "zed", "Trae", "trae",
               "Windsurf", "windsurf", "Copilot", "copilot",
               "GitHub Copilot"}
