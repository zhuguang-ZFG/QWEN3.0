"""PollinationsAI free backends."""

BACKENDS = {
    "pollinations": {
        "url": "https://text.pollinations.ai/openai",
        "key": "none",
        "model": "openai",
        "fmt": "openai",
        "timeout": 30,
    },
    "pollinations_openai": {
        "url": "https://text.pollinations.ai/openai/chat/completions",
        "key": "none",
        "model": "openai",
        "fmt": "openai",
        "timeout": 30,
    },
    "pollinations_openai_large": {
        "url": "https://text.pollinations.ai/openai/chat/completions",
        "key": "none",
        "model": "openai-large",
        "fmt": "openai",
        "timeout": 45,
    },
    "pollinations_deepseek": {
        "url": "https://text.pollinations.ai/openai/chat/completions",
        "key": "none",
        "model": "deepseek",
        "fmt": "openai",
        "timeout": 30,
    },
    "pollinations_qwen_coder": {
        "url": "https://text.pollinations.ai/openai/chat/completions",
        "key": "none",
        "model": "qwen-coder",
        "fmt": "openai",
        "timeout": 30,
    },
}
