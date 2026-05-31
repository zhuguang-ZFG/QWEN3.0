"""Runtime topology detection (M6: all backends cloud-native, no local dependencies)."""

import os

TRUTHY = {"1", "true", "yes", "on"}
HOST_DEPENDENT_OPT_IN = "LIMA_ENABLE_HOST_DEPENDENT_BACKENDS"

# M6: All host-dependent backends migrated to VPS or deleted. Set is empty.
LOCAL_ONLY_BACKENDS: set[str] = set()

# M6: All tunnel entries cleared — no FRP needed.
BACKEND_PORT_ENV: dict[str, tuple[int, str]] = {}


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUTHY


def backend_available(name: str) -> bool:
    """M6: All backends are cloud-native — always available."""
    return True


def is_host_dependent_backend(name: str) -> bool:
    """M6: No host-dependent backends remain."""
    return False


def filter_backends(names: list[str]) -> list[str]:
    """M6: No filtering needed — all backends are available."""
    return list(names)
