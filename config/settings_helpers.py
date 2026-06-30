"""Dynamic env-resolution helpers for settings.

Pure functions with no dataclass state; kept here so ``settings_core`` stays
under the 300-line limit and focuses on dataclass definitions only.
"""

from __future__ import annotations

import os
import re


def get_key_pool_raw(provider: str) -> str:
    """Return the raw key-pool value for *provider* from the environment."""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", provider).strip("_").upper()
    return os.environ.get(f"LIMA_KEY_POOL_{safe}", "")


def resolve_backend_key(key: str) -> str:
    """Resolve a backend key, expanding ``$ENV_VAR`` references at call time."""
    if key.startswith("$"):
        return os.environ.get(key.lstrip("$"), "")
    return key


def get_env(name: str, default: str = "") -> str:
    """Read a dynamic environment variable at call time.

    Used for env names that are not known until runtime (e.g. per-backend key_env_var).
    """
    return os.environ.get(name, default)
