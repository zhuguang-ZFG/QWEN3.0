"""商业 API 后端定义（Naga、FreeTheAI、Zuki、Cerebras、中国厂商等）"""
import os

BACKENDS = {
    # ── Cerebras (芯片级加速) ──
    'cerebras_qwen235b': {'url': 'https://api.cerebras.ai/v1/chat/completions', 'key': os.environ.get('CEREBRAS_API_KEY', ''), 'model': 'qwen-3-235b-a22b-instruct-2507', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'cerebras_llama8b': {'url': 'https://api.cerebras.ai/v1/chat/completions', 'key': os.environ.get('CEREBRAS_API_KEY', ''), 'model': 'llama3.1-8b', 'fmt': 'openai', 'timeout': 15},
    'cerebras_gptoss': {'url': 'https://api.cerebras.ai/v1/chat/completions', 'key': os.environ.get('CEREBRAS_API_KEY', ''), 'model': 'gpt-oss-120b', 'fmt': 'openai', 'timeout': 20},

    # ── Naga AI ──
    'naga_llama70b': {'url': 'https://api.naga.ai/v1/chat/completions', 'key': os.environ.get('NAGA_API_KEY', ''), 'model': 'llama-3.3-70b', 'fmt': 'openai', 'timeout': 20},
    'naga_gpt41mini': {'url': 'https://api.naga.ai/v1/chat/completions', 'key': os.environ.get('NAGA_API_KEY', ''), 'model': 'gpt-4.1-mini', 'fmt': 'openai', 'timeout': 20},
    'naga_glm45': {'url': 'https://api.naga.ai/v1/chat/completions', 'key': os.environ.get('NAGA_API_KEY', ''), 'model': 'glm-4.5-air', 'fmt': 'openai', 'timeout': 20},
    'naga_llama4': {'url': 'https://api.naga.ai/v1/chat/completions', 'key': os.environ.get('NAGA_API_KEY', ''), 'model': 'llama-4-scout', 'fmt': 'openai', 'timeout': 20},

    # ── FreeTheAI ──
    'freetheai_ds': {'url': 'https://api.freetheai.xyz/v1/chat/completions', 'key': os.environ.get('FREETHEAI_API_KEY', ''), 'model': 'yng/gemini-3-1-pro', 'fmt': 'openai', 'timeout': 20},
    'freetheai_gpt41': {'url': 'https://api.freetheai.xyz/v1/chat/completions', 'key': os.environ.get('FREETHEAI_API_KEY', ''), 'model': 'bbl/gpt-4.1', 'fmt': 'openai', 'timeout': 20},
    'freetheai_swe': {'url': 'https://api.freetheai.xyz/v1/chat/completions', 'key': os.environ.get('FREETHEAI_API_KEY', ''), 'model': 'wsf/swe-1.6', 'fmt': 'openai', 'timeout': 20},

    # ── Zuki Journey ──
    'zuki_codestral': {'url': 'https://zukijourney.com/v1/chat/completions', 'key': os.environ.get('ZUKI_API_KEY', ''), 'model': 'codestral-latest', 'fmt': 'openai', 'timeout': 20},
    'zuki_mistral_small': {'url': 'https://zukijourney.com/v1/chat/completions', 'key': os.environ.get('ZUKI_API_KEY', ''), 'model': 'mistral-small-latest', 'fmt': 'openai', 'timeout': 20},

    # ── 其他商业平台 ──
    'featherless': {'url': 'https://api.featherless.ai/v1/chat/completions', 'key': os.environ.get('FEATHERLESS_API_KEY', ''), 'model': 'Qwen/Qwen3-32B', 'fmt': 'openai', 'timeout': 20},
    'glhf': {'url': 'https://glhf.chat/api/openai/v1/chat/completions', 'key': os.environ.get('GLHF_API_KEY', ''), 'model': 'hf:Qwen/Qwen3-32B', 'fmt': 'openai', 'timeout': 20},
    'agentrouter': {'url': 'https://agentrouter.org/v1/chat/completions', 'key': os.environ.get('AGENTROUTER_API_KEY', ''), 'model': 'qwen/qwen3-32b', 'fmt': 'openai', 'timeout': 20},

    # ── 中国厂商 ──
    'zhipu_flash': {'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions', 'key': os.environ.get('ZHIPU_API_KEY', ''), 'model': 'glm-4-flash', 'fmt': 'openai', 'timeout': 10},
    'zhipu_flash7': {'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions', 'key': os.environ.get('ZHIPU_API_KEY', ''), 'model': 'glm-4.7-flash', 'fmt': 'openai', 'timeout': 10},
    'silicon_qwen8b': {'url': 'https://api.siliconflow.cn/v1/chat/completions', 'key': os.environ.get('SILICONFLOW_API_KEY', ''), 'model': 'Qwen/Qwen3-8B', 'fmt': 'openai', 'timeout': 10},
    'silicon_glm9b': {'url': 'https://api.siliconflow.cn/v1/chat/completions', 'key': os.environ.get('SILICONFLOW_API_KEY', ''), 'model': 'THUDM/glm-4-9b-chat', 'fmt': 'openai', 'timeout': 10},
    'silicon_deepseek': {'url': 'https://api.siliconflow.cn/v1/chat/completions', 'key': os.environ.get('SILICONFLOW_API_KEY', ''), 'model': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B', 'fmt': 'openai', 'timeout': 15},
    'baidu_ernie': {'url': 'https://qianfan.baidubce.com/v2/chat/completions', 'key': os.environ.get('BAIDU_API_KEY', ''), 'model': 'ernie-3.5-8k', 'fmt': 'openai', 'auth': 'bearer', 'timeout': 10},
    'baidu_speed': {'url': 'https://qianfan.baidubce.com/v2/chat/completions', 'key': os.environ.get('BAIDU_API_KEY', ''), 'model': 'ernie-speed-8k', 'fmt': 'openai', 'auth': 'bearer', 'timeout': 8},
    'volcengine_doubao': {'url': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions', 'key': os.environ.get('VOLCENGINE_API_KEY', ''), 'model': 'doubao-1-5-pro-256k', 'fmt': 'openai', 'timeout': 15},
    'aliyun_qwen3': {'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', 'key': os.environ.get('ALIYUN_API_KEY', ''), 'model': 'qwen3-8b', 'fmt': 'openai', 'timeout': 10, 'force_stream_param': True},
    'aliyun_coder': {'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', 'key': os.environ.get('ALIYUN_API_KEY', ''), 'model': 'qwen-3-coder-plus', 'fmt': 'openai', 'timeout': 15},
    'tencent_hunyuan': {'url': 'https://api.hunyuan.cloud.tencent.com/v1/chat/completions', 'key': os.environ.get('TENCENT_API_KEY', ''), 'model': 'hunyuan-lite', 'fmt': 'openai', 'timeout': 10},
    'chinamobile': {'url': 'https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions', 'key': os.environ.get('CHINAMOBILE_API_KEY', ''), 'model': 'minimax-m25', 'fmt': 'openai', 'caps': ['tool_calls']},
    'tokenrouter_minimax_m3': {'url': 'https://api.tokenrouter.com/v1/chat/completions', 'key': os.environ.get('TOKENROUTER_API_KEY', ''), 'model': 'MiniMax-M3', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},

    # ── FreeModel.dev ──
    'fm_gpt55': {'url': 'https://api.freemodel.dev/v1/chat/completions', 'key': os.environ.get('FREEMODEL_API_KEY', ''), 'model': 'gpt-5.5', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls']},
    'fm_gpt54': {'url': 'https://api.freemodel.dev/v1/chat/completions', 'key': os.environ.get('FREEMODEL_API_KEY', ''), 'model': 'gpt-5.4', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls']},
    'fm_gpt54_mini': {'url': 'https://api.freemodel.dev/v1/chat/completions', 'key': os.environ.get('FREEMODEL_API_KEY', ''), 'model': 'gpt-5.4-mini', 'fmt': 'openai', 'timeout': 30},
    'fm_gpt53_codex': {'url': 'https://api.freemodel.dev/v1/chat/completions', 'key': os.environ.get('FREEMODEL_API_KEY', ''), 'model': 'gpt-5.3-codex', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls']},

    # ── Unclose.io ──
    'unclose_hermes': {'url': 'https://hermes.ai.unturf.com/v1/chat/completions', 'key': 'none', 'model': 'adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic', 'fmt': 'openai', 'timeout': 15},
    'unclose_qwen': {'url': 'https://qwen.ai.unturf.com/v1/chat/completions', 'key': 'none', 'model': 'Qwen3.6-27B-UD-Q4_K_XL.gguf', 'fmt': 'openai', 'timeout': 30, 'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}},

    # ── Fireworks AI ──
    'fireworks_llama405b': {'url': 'https://api.fireworks.ai/inference/v1/chat/completions', 'key': os.environ.get('FIREWORKS_API_KEY', ''), 'model': 'accounts/fireworks/models/llama-v3p1-405b-instruct', 'fmt': 'openai', 'timeout': 45},

    # ── OVHcloud ──
    'ovh_llama70b': {'url': 'https://llama-3-3-70b-instruct.endpoints.ai.cloud.ovh.net/v1/chat/completions', 'key': 'none', 'model': 'Llama-3.3-70B-Instruct', 'fmt': 'openai', 'timeout': 30},
    'ovh_deepseek': {'url': 'https://deepseek-r1-distill-qwen-32b.endpoints.ai.cloud.ovh.net/v1/chat/completions', 'key': 'none', 'model': 'DeepSeek-R1-Distill-Qwen-32B', 'fmt': 'openai', 'timeout': 45},

    # ── Cohere ──
    'cohere_command': {'url': 'https://api.cohere.com/compatibility/v1/chat/completions', 'key': os.environ.get('COHERE_API_KEY', ''), 'model': 'command-a-03-2025', 'fmt': 'openai', 'timeout': 30},
    'cohere_command_plus': {'url': 'https://api.cohere.com/compatibility/v1/chat/completions', 'key': os.environ.get('COHERE_API_KEY', ''), 'model': 'command-a-plus-05-2026', 'fmt': 'openai', 'timeout': 30},
    'cohere_reasoning': {'url': 'https://api.cohere.com/compatibility/v1/chat/completions', 'key': os.environ.get('COHERE_API_KEY', ''), 'model': 'command-a-reasoning-08-2025', 'fmt': 'openai', 'timeout': 45},
    'cohere_vision': {'url': 'https://api.cohere.com/compatibility/v1/chat/completions', 'key': os.environ.get('COHERE_API_KEY', ''), 'model': 'command-a-vision-07-2025', 'fmt': 'openai', 'timeout': 30},

    # ── SambaNova Cloud ──
    'sambanova_llama4': {'url': 'https://api.sambanova.ai/v1/chat/completions', 'key': os.environ.get('SAMBANOVA_API_KEY', ''), 'model': 'Meta-Llama-4-Maverick-17B-128E-Instruct', 'fmt': 'openai', 'timeout': 20},
    'sambanova_ds_v3': {'url': 'https://api.sambanova.ai/v1/chat/completions', 'key': os.environ.get('SAMBANOVA_API_KEY', ''), 'model': 'DeepSeek-V3.2', 'fmt': 'openai', 'timeout': 30},
    'sambanova_coder': {'url': 'https://api.sambanova.ai/v1/chat/completions', 'key': os.environ.get('SAMBANOVA_API_KEY', ''), 'model': 'DeepSeek-Coder-V2-Lite-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'sambanova_qwen_coder': {'url': 'https://api.sambanova.ai/v1/chat/completions', 'key': os.environ.get('SAMBANOVA_API_KEY', ''), 'model': 'Qwen2.5-Coder-32B-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},

    # ── DeepInfra ──
    'deepinfra_llama4': {'url': 'https://api.deepinfra.com/v1/openai/chat/completions', 'key': os.environ.get('DEEPINFRA_API_KEY', ''), 'model': 'meta-llama/Llama-4-Maverick-17B-128E-Instruct', 'fmt': 'openai', 'timeout': 20},
    'deepinfra_qwen235b': {'url': 'https://api.deepinfra.com/v1/openai/chat/completions', 'key': os.environ.get('DEEPINFRA_API_KEY', ''), 'model': 'Qwen/Qwen3-235B-A22B-Instruct', 'fmt': 'openai', 'timeout': 30},
    'deepinfra_coder': {'url': 'https://api.deepinfra.com/v1/openai/chat/completions', 'key': os.environ.get('DEEPINFRA_API_KEY', ''), 'model': 'Qwen/Qwen2.5-Coder-32B-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'deepinfra_codellama': {'url': 'https://api.deepinfra.com/v1/openai/chat/completions', 'key': os.environ.get('DEEPINFRA_API_KEY', ''), 'model': 'codellama/CodeLlama-70b-Instruct-hf', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},

    # ── Together.ai ──
    'together_qwen_coder': {'url': 'https://api.together.xyz/v1/chat/completions', 'key': os.environ.get('TOGETHER_API_KEY', ''), 'model': 'Qwen/Qwen2.5-Coder-32B-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'together_codellama': {'url': 'https://api.together.xyz/v1/chat/completions', 'key': os.environ.get('TOGETHER_API_KEY', ''), 'model': 'codellama/CodeLlama-70b-Instruct-hf', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'together_deepseek_coder': {'url': 'https://api.together.xyz/v1/chat/completions', 'key': os.environ.get('TOGETHER_API_KEY', ''), 'model': 'deepseek-ai/deepseek-coder-33b-instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},

    # ── OpenGateway (Sionic AI) ──
    'ogw_gpt55': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'openai/gpt-5.5', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls']},
    'ogw_gpt54': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'openai/gpt-5.4', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls']},
    'ogw_gpt54_mini': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'openai/gpt-5.4-mini', 'fmt': 'openai', 'timeout': 30},
    'ogw_gpt5_codex': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'openai/gpt-5-codex', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls', 'code']},
    'ogw_gpt5_nano': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'openai/gpt-5-nano', 'fmt': 'openai', 'timeout': 15},
    'ogw_gpt4o_mini': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'openai/gpt-4o-mini', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
    'ogw_claude_sonnet': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'anthropic/claude-sonnet-4-6', 'fmt': 'openai', 'timeout': 45, 'caps': ['tool_calls']},
    'ogw_claude_haiku': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'anthropic/claude-haiku-4-5', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'ogw_deepseek_v4': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'deepseek/deepseek-v4-pro', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls']},
    'ogw_deepseek_flash': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'deepseek/deepseek-v4-flash', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
    'ogw_grok': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'x-ai/grok-4.3', 'fmt': 'openai', 'timeout': 45, 'caps': ['tool_calls']},
    'ogw_kimi': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'moonshotai/kimi-k2.6', 'fmt': 'openai', 'timeout': 45, 'caps': ['tool_calls']},
    'ogw_glm5': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'z-ai/glm-5.1', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'ogw_gemini_flash': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'google/gemini-2.5-flash', 'fmt': 'openai', 'timeout': 20},
    'ogw_minimax': {'url': 'https://api.opengateway.ai/v1/chat/completions', 'key': os.environ.get('OPENGATEWAY_API_KEY', ''), 'model': 'minimax/MiniMax-M2.7', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},

    # ── Agnes AI ──
    'agnes20': {'url': 'https://apihub.agnes-ai.com/v1/chat/completions', 'key': os.environ.get('AGNES_AI_API_KEY', ''), 'model': 'agnes-2.0-flash', 'fmt': 'openai', 'timeout': 45, 'caps': ['tool_calls', 'code']},
    'agnes15': {'url': 'https://apihub.agnes-ai.com/v1/chat/completions', 'key': os.environ.get('AGNES_AI_API_KEY', ''), 'model': 'agnes-1.5-flash', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
}
