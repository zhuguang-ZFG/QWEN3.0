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
    # M2: scnet_large/scnet_code now served by VPS sidecar (lima-scnet-reverse.service :4505)
    "mimo_web",
    "mimo_web_think",
    "mimo_web_flash",
    "mimo_web_code",
    "mimo_web_think_code",
    # M1: oldllm_* already on CF Worker (llm.zhuguang.ccwu.cc), no longer host-dependent
    # M1: local_* Ollama models removed, no longer part of LiMa
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
    # M2: scnet_large_* tunnel entries removed (now VPS sidecar, no FRP needed)
    # M1: local_* Ollama 模型已删除
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
