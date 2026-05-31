import os
import socket


TRUTHY = {"1", "true", "yes", "on"}
HOST_DEPENDENT_OPT_IN = "LIMA_ENABLE_HOST_DEPENDENT_BACKENDS"

LOCAL_ONLY_BACKENDS: set[str] = {
    "deepseek_free",
    "ddg_gpt4o_mini",
    "ddg_gpt5_mini",
    "ddg_claude_haiku_45",
    "ddg_llama4",
    "ddg_mistral",
    "ddg_tinfoil_gptoss_120b",
    "kimi",
    "kimi_thinking",
    "kimi_search",
    "longcat_web",
    "longcat_web_think",
    "longcat_web_research",
    "scnet_large_ds_flash",
    "scnet_large_ds_pro",
    "scnet_qwen235b_code",
    "scnet_ds_pro_code",
    "mimo_web",
    "mimo_web_think",
    "mimo_web_flash",
    "mimo_web_code",
    "mimo_web_think_code",
    "oldllm_gpt54",
    "oldllm_gpt53",
    "oldllm_gpt52",
    "oldllm_gpt51",
    "oldllm_gpt5",
    "oldllm_gpt5_mini",
    "oldllm_gpt41",
    "oldllm_gpt41_mini",
    "oldllm_gpt41_nano",
    "oldllm_gpt4",
    "oldllm_o1",
    "oldllm_o4_mini",
    "local_coder14b",
    "local_reasoning",
    "local_general",
    "local_fast",
    "local_chat",
    "local_qwen3",
    "local_phi4",
    "local_mistral",
}

BACKEND_PORT_ENV: dict[str, tuple[int, str]] = {
    "ddg_gpt4o_mini": (4500, "DDG_TUNNEL_URL"),
    "ddg_gpt5_mini": (4500, "DDG_TUNNEL_URL"),
    "ddg_claude_haiku_45": (4500, "DDG_TUNNEL_URL"),
    "ddg_llama4": (4500, "DDG_TUNNEL_URL"),
    "ddg_mistral": (4500, "DDG_TUNNEL_URL"),
    "ddg_tinfoil_gptoss_120b": (4500, "DDG_TUNNEL_URL"),
    "kimi": (4504, "KIMI_TUNNEL_URL"),
    "kimi_thinking": (4504, "KIMI_TUNNEL_URL"),
    "kimi_search": (4504, "KIMI_TUNNEL_URL"),
    "scnet_large_ds_flash": (4505, "SCNET_LARGE_TUNNEL_URL"),
    "scnet_large_ds_pro": (4505, "SCNET_LARGE_TUNNEL_URL"),
    "local_coder14b": (11434, "OLLAMA_TUNNEL_URL"),
    "local_reasoning": (11434, "OLLAMA_TUNNEL_URL"),
    "local_general": (11434, "OLLAMA_TUNNEL_URL"),
    "local_fast": (11434, "OLLAMA_TUNNEL_URL"),
    "local_chat": (11434, "OLLAMA_TUNNEL_URL"),
    "local_qwen3": (11434, "OLLAMA_TUNNEL_URL"),
    "local_phi4": (11434, "OLLAMA_TUNNEL_URL"),
    "local_mistral": (11434, "OLLAMA_TUNNEL_URL"),
}


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUTHY


def has_tunnel_override(name: str) -> bool:
    cfg = BACKEND_PORT_ENV.get(name)
    if not cfg:
        return False
    return bool(os.environ.get(cfg[1], "").strip())


def local_port_open(port: int, host: str = "127.0.0.1",
                    timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def backend_available(name: str) -> bool:
    if name not in LOCAL_ONLY_BACKENDS:
        return True
    if not env_truthy(HOST_DEPENDENT_OPT_IN):
        return False
    if has_tunnel_override(name):
        return True
    cfg = BACKEND_PORT_ENV.get(name)
    return local_port_open(cfg[0]) if cfg else False


def is_host_dependent_backend(name: str) -> bool:
    return name in LOCAL_ONLY_BACKENDS


def filter_backends(names: list[str]) -> list[str]:
    return [name for name in names if backend_available(name)]
