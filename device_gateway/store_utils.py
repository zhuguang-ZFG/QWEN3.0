"""Shared store infrastructure: base class + config mixin + manager pattern.

Three device store families (task, ledger, memory) share the same pattern:
- A Protocol interface
- An InMemory implementation with RLock
- A global singleton with configure/set_for_tests/health helpers

This module provides DeviceStoreBase as the runtime abstraction,
StoreConfigMixin for the implementation pattern, and StoreManager for the
global+configure+set+health pattern.
"""

from __future__ import annotations

import abc
import os
import threading
from typing import Any, Callable, Generic, TypeVar


class DeviceStoreBase(abc.ABC):
    """Runtime base class shared by all device store backends.

    Only backend metadata is declared here because the three concrete store
    families have incompatible ``reset`` signatures (task/ledger reset all
    state; memory reset is scoped to a device_id and returns a count).
    """

    backend_name: str
    shared_across_processes: bool


T = TypeVar("T")


class StoreConfigMixin(DeviceStoreBase):
    """Mixin for in-memory store implementations: provides _lock and backend metadata."""

    backend_name: str = "memory"
    shared_across_processes: bool = False

    def __init__(self) -> None:
        self._lock = threading.RLock()


class StoreManager(Generic[T]):
    """Manages a global store singleton with configure/set/health pattern.

    Usage:
        task_manager = StoreManager[DeviceTaskStore](InMemoryDeviceTaskStore)
        task_manager.configure_from_env(...)  # env-based config
        task_manager.store  # current store instance
        task_manager.health()  # {'backend': ..., 'shared_across_processes': ...}
    """

    def __init__(self, default_factory: type[T]) -> None:
        self._default_factory = default_factory
        self._store: T = default_factory()

    @property
    def store(self) -> T:
        return self._store

    def set(self, store: T) -> None:
        self._store = store

    def health(self) -> dict[str, Any]:
        return {
            "backend": getattr(self._store, "backend_name", self._store.__class__.__name__),
            "shared_across_processes": bool(getattr(self._store, "shared_across_processes", False)),
        }

    def configure_from_env(
        self,
        env_var: str,
        redis_url: str | None,
        redis_factory: Callable[[str], T],
        *,
        use_redis_when_url_present: bool = False,
        required_redis_var: str = "LIMA_DEVICE_REDIS_URL",
    ) -> None:
        """Select a backend from env and replace the active store singleton.

        Args:
            env_var: Environment variable name controlling the backend.
            redis_url: Redis URL to use when redis is selected.
            redis_factory: Callable accepting the Redis URL and returning a
                store instance (typically a RedisBackend constructor).
            use_redis_when_url_present: When True, default to redis if no
                backend is explicitly configured but a Redis URL is present.
            required_redis_var: Name of the Redis URL variable for error
                messages.
        """
        backend = os.environ.get(env_var, "").strip().lower()
        if backend == "redis" or (use_redis_when_url_present and backend == "" and redis_url):
            if not redis_url:
                raise RuntimeError(f"{required_redis_var} is required when {env_var}=redis")
            self.set(redis_factory(redis_url))
        else:
            self.set(self._default_factory())
