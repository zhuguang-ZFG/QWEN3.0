"""DuckAI local reverse proxy fallback backends."""

from config.backend_config import DDG_TUNNEL_URL

BACKENDS = {
    "ddg_gpt4o_mini": {
        "url": f"{DDG_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "gpt-4o-mini",
        "fmt": "openai",
        "timeout": 30,
        "no_system": True,
        "caps": ["tool_calls"],
    },
    "ddg_gpt5_mini": {
        "url": f"{DDG_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "gpt-5-mini",
        "fmt": "openai",
        "timeout": 30,
        "no_system": True,
        "caps": ["tool_calls"],
    },
    "ddg_claude_haiku_45": {
        "url": f"{DDG_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "claude-haiku-4-5",
        "fmt": "openai",
        "timeout": 30,
        "no_system": True,
    },
    "ddg_tinfoil_gptoss_120b": {
        "url": f"{DDG_TUNNEL_URL}/v1/chat/completions",
        "key": "none",
        "model": "tinfoil/gpt-oss-120b",
        "fmt": "openai",
        "timeout": 45,
        "no_system": True,
    },
}
