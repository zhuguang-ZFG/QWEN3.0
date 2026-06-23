"""OpenRouter 后端定义"""

from config.backend_config import OPENROUTER_API_KEY

BACKENDS = {
    "or_deepseek_r1": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "deepseek/deepseek-v4-flash:free",
        "fmt": "openai",
        "timeout": 60,
    },
    "or_qwen3_coder": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "qwen/qwen3-coder:free",
        "fmt": "openai",
        "timeout": 60,
    },
    "or_llama70b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "fmt": "openai",
        "timeout": 45,
    },
    "or_nemotron": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1:free",
        "fmt": "openai",
        "timeout": 60,
    },
    "or_qwen3_80b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
        "fmt": "openai",
        "timeout": 30,
    },
    "or_nemotron120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "fmt": "openai",
        "timeout": 60,
    },
    "or_gptoss_120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "openai/gpt-oss-120b:free",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
    },
    "or_glm45": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "z-ai/glm-4.5-air:free",
        "fmt": "openai",
        "timeout": 30,
    },
    "or_minimax": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "minimax/minimax-m2.5:free",
        "fmt": "openai",
        "timeout": 30,
    },
    "or_gemma4": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "google/gemma-4-31b-it:free",
        "fmt": "openai",
        "timeout": 30,
    },
    "or_llama4_scout": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "model": "meta-llama/llama-4-scout:free",
        "fmt": "openai",
        "timeout": 30,
    },
}
