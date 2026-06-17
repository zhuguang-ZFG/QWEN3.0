"""NVIDIA NIM 后端定义"""

import os

BACKENDS = {
    "nvidia_nemotron": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1",
        "fmt": "openai",
    },
    "nvidia_llama70b": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "meta/llama-3.3-70b-instruct",
        "fmt": "openai",
    },
    "nvidia_qwen_coder": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "qwen/qwen3-coder-480b-a35b-instruct",
        "fmt": "openai",
    },
    "nvidia_llama4": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "meta/llama-4-maverick-17b-128e-instruct",
        "fmt": "openai",
    },
    "nvidia_mistral": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "mistralai/mistral-large-3-675b-instruct-2512",
        "fmt": "openai",
        "caps": ["tool_calls"],
    },
    "nvidia_phi4": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "microsoft/phi-4-mini-instruct",
        "fmt": "openai",
    },
    # ── NVIDIA NIM 强力模型 (40 RPM free tier) ──
    "nvidia_deepseek_v4": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "deepseek-ai/deepseek-v4-pro",
        "fmt": "openai",
        "timeout": 45,
        "caps": ["tool_calls"],
    },
    "nvidia_qwen35_coder": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "qwen/qwen3.5-397b-a17b",
        "fmt": "openai",
        "timeout": 45,
        "caps": ["tool_calls"],
    },
    "nvidia_glm5": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "z-ai/glm-5.1",
        "fmt": "openai",
        "timeout": 30,
    },
    "nvidia_kimi_k25": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY", ""),
        "model": "moonshotai/kimi-k2.5",
        "fmt": "openai",
        "timeout": 45,
        "caps": ["tool_calls"],
    },
}
