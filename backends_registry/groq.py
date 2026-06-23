"""Groq 后端定义"""

from config.backend_config import GROQ_API_KEY

BACKENDS = {
    "groq_llama70b": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": GROQ_API_KEY,
        "model": "llama-3.3-70b-versatile",
        "fmt": "openai",
        "timeout": 15,
        "caps": ["tool_calls"],
    },
    "groq_gptoss": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": GROQ_API_KEY,
        "model": "openai/gpt-oss-120b",
        "fmt": "openai",
        "timeout": 15,
        "caps": ["tool_calls"],
    },
    "groq_gptoss_20b": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": GROQ_API_KEY,
        "model": "openai/gpt-oss-20b",
        "fmt": "openai",
        "timeout": 10,
    },
    "groq_qwen32b": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": GROQ_API_KEY,
        "model": "qwen/qwen3-32b",
        "fmt": "openai",
        "timeout": 15,
        "caps": ["tool_calls"],
    },
    "groq_llama4": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": GROQ_API_KEY,
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "fmt": "openai",
        "timeout": 15,
        "caps": ["tool_calls"],
    },
    "groq_llama8b": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": GROQ_API_KEY,
        "model": "llama-3.1-8b-instant",
        "fmt": "openai",
        "timeout": 10,
    },
}
