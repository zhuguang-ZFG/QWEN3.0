"""杂项后端定义（local、hermes_agent 等）"""

from config.backend_config import OLLAMA_TUNNEL_URL

# LM_URL 从 __init__.py 导入
BACKENDS = {
    "local": {
        "url": "http://localhost:1234/v1/chat/completions",
        "key": "",
        "model": "local-model",
        "fmt": "openai",
        "auth": "bearer",
    },
    "hermes_agent": {
        "url": "http://127.0.0.1:8699/v1/chat/completions",
        "key": "none",
        "model": "hermes-agent",
        "fmt": "openai",
        "timeout": 120,
        "caps": ["tool_calls"],
    },
    "deepseek_free": {
        "url": "http://127.0.0.1:8000/v1/chat/completions",
        "key": "none",
        "model": "deepseek-default",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "admission": "code_medium_candidate",
        "private_code_allowed": True,
    },
    "local_coder14b": {
        "url": f"{OLLAMA_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "qwen2.5-coder:14b",
        "fmt": "openai",
        "timeout": 30,
    },
    "local_reasoning": {
        "url": f"{OLLAMA_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "deepseek-r1:7b",
        "fmt": "openai",
        "timeout": 45,
        "caps": ["deep_reasoning"],
    },
    "local_general": {
        "url": f"{OLLAMA_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "gemma3:12b",
        "fmt": "openai",
        "timeout": 30,
    },
    "local_fast": {
        "url": f"{OLLAMA_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "qwen2.5-coder:1.5b",
        "fmt": "openai",
        "timeout": 10,
    },
    "local_chat": {
        "url": f"{OLLAMA_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "qwen2.5:0.5b",
        "fmt": "openai",
        "timeout": 5,
    },
}
