"""ModelScope 后端定义（魔搭免费 API 推理）"""
import os

BACKENDS = {
    # ── ModelScope 基础模型 ──
    'ms_qwen_coder_32b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen2.5-Coder-32B-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['code']},
    'ms_qwen_coder_14b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen2.5-Coder-14B-Instruct', 'fmt': 'openai', 'timeout': 20, 'caps': ['code']},
    'ms_qwen_coder_7b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen2.5-Coder-7B-Instruct', 'fmt': 'openai', 'timeout': 15, 'caps': ['code']},
    'ms_deepseek_v4': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'deepseek-ai/DeepSeek-V4-Flash', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'ms_qwen35_27b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3.5-27B', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'ms_kimi_k25': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'moonshotai/Kimi-K2.5', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'ms_glm5': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'ZhipuAI/GLM-5', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},

    # ── ModelScope 扩展模型 (2026-06-06: 16 个新模型) ──
    'ms_ds_v32': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'deepseek-ai/DeepSeek-V3.2', 'fmt': 'openai', 'timeout': 45, 'force_stream_param': True, 'caps': ['tool_calls', 'code']},
    'ms_ds_r1': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'deepseek-ai/DeepSeek-R1-0528', 'fmt': 'openai', 'timeout': 60, 'caps': ['code']},
    'ms_qwen3_235b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3-235B-A22B', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls', 'code']},
    'ms_qwen3_235b_think': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3-235B-A22B-Thinking-2507', 'fmt': 'openai', 'timeout': 90, 'caps': ['code']},
    'ms_qwen3_32b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3-32B', 'fmt': 'openai', 'timeout': 30, 'caps': ['code']},
    'ms_qwen3_coder_30b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3-Coder-30B-A3B-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls', 'code']},
    'ms_qwen3_next_80b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3-Next-80B-A3B-Instruct', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls', 'code']},
    'ms_qwen3_next_80b_think': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3-Next-80B-A3B-Thinking', 'fmt': 'openai', 'timeout': 90, 'caps': ['code']},
    'ms_qwen35_35b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3.5-35B-A3B', 'fmt': 'openai', 'timeout': 45, 'caps': ['code']},
    'ms_qwen35_122b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3.5-122B-A10B', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls', 'code']},
    'ms_qwen35_397b': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Qwen/Qwen3.5-397B-A17B', 'fmt': 'openai', 'timeout': 90, 'caps': ['code']},
    'ms_glm51': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'ZhipuAI/GLM-5.1', 'fmt': 'openai', 'timeout': 45, 'force_stream_param': True, 'caps': ['tool_calls']},
    'ms_step37': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'stepfun-ai/Step-3.7-Flash', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'ms_mistral_large': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'mistralai/Mistral-Large-Instruct-2407', 'fmt': 'openai', 'timeout': 30, 'caps': ['code']},
    'ms_llama4': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'LLM-Research/Llama-4-Maverick-17B-128E-Instruct', 'fmt': 'openai', 'timeout': 30, 'caps': ['code']},
    'ms_interns2': {'url': 'https://api-inference.modelscope.cn/v1/chat/completions', 'key': os.environ.get('MODELSCOPE_API_KEY', ''), 'model': 'Shanghai_AI_Laboratory/Intern-S2-Preview', 'fmt': 'openai', 'timeout': 30, 'caps': ['code']},
}
