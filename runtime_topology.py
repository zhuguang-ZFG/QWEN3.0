import os
import socket


TRUTHY = {"1", "true", "yes", "on"}
HOST_DEPENDENT_OPT_IN = "LIMA_ENABLE_HOST_DEPENDENT_BACKENDS"

# M6: DDG + deepseek_free deleted (not in any routing pool, dead code).
# LOCAL_ONLY_BACKENDS is now empty — all backends are cloud-native.
LOCAL_ONLY_BACKENDS: set[str] = set()

# M6: DDG tunnel entries removed. All tunnel entries cleared — no FRP needed.
BACKEND_PORT_ENV: dict[str, tuple[int, str]] = {}


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
