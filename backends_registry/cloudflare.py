"""Cloudflare Workers AI 后端定义"""
import os

BACKENDS = {
    # ── Cloudflare Workers AI (官方 API) ──
    'cf_llama70b': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/meta/llama-3.3-70b-instruct-fp8-fast', 'fmt': 'openai', 'timeout': 15},
    'cf_llama4': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/meta/llama-4-scout-17b-16e-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_qwen_coder': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/qwen/qwen2.5-coder-32b-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_codellama': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/meta/codellama-7b-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_starcoder': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/bigcode/starcoder2-15b', 'fmt': 'openai', 'timeout': 15},
    'cf_mistral': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/mistralai/mistral-small-3.1-24b-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_vision': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/meta/llama-3.2-11b-vision-instruct', 'fmt': 'openai', 'timeout': 15},

    # ── Cloudflare 扩展模型 (37 个模型嗅探后挑选) ──
    'cf_kimi_k26': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/moonshotai/kimi-k2.6', 'fmt': 'openai', 'timeout': 30},
    'cf_deepseek_r1': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/deepseek-ai/deepseek-r1-distill-qwen-32b', 'fmt': 'openai', 'timeout': 45},
    'cf_qwq': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/qwen/qwq-32b', 'fmt': 'openai', 'timeout': 45},
    'cf_gptoss_120b': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/openai/gpt-oss-120b', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'cf_qwen3_30b': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/qwen/qwen3-30b-a3b-fp8', 'fmt': 'openai', 'timeout': 20},
    'cf_nemotron': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/nvidia/nemotron-3-120b-a12b', 'fmt': 'openai', 'timeout': 30},
    'cf_glm47': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/zai-org/glm-4.7-flash', 'fmt': 'openai', 'timeout': 15},
    'cf_gemma4': {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions", 'key': os.environ.get('CLOUDFLARE_TOKEN', ''), 'model': '@cf/google/gemma-4-26b-a4b-it', 'fmt': 'openai', 'timeout': 20},

    # ── Cloudflare Workers AI (CF Worker 代理, 免费 10K neurons/天) ──
    'cfai_llama70b': {'url': 'https://ai.zhuguang.ccwu.cc/v1/chat/completions', 'key': 'none', 'model': 'llama-3.3-70b', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'cfai_llama4': {'url': 'https://ai.zhuguang.ccwu.cc/v1/chat/completions', 'key': 'none', 'model': 'llama-4-scout', 'fmt': 'openai', 'timeout': 30},
    'cfai_qwen_coder': {'url': 'https://ai.zhuguang.ccwu.cc/v1/chat/completions', 'key': 'none', 'model': 'qwen2.5-coder-32b', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls', 'code']},
    'cfai_deepseek_r1': {'url': 'https://ai.zhuguang.ccwu.cc/v1/chat/completions', 'key': 'none', 'model': 'deepseek-r1-32b', 'fmt': 'openai', 'timeout': 45},
    'cfai_mistral': {'url': 'https://ai.zhuguang.ccwu.cc/v1/chat/completions', 'key': 'none', 'model': 'mistral-small-3.1', 'fmt': 'openai', 'timeout': 30},
}
