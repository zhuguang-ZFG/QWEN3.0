"""Shared store infrastructure: config mixin + manager pattern.

Three device store families (task, ledger, memory) share the same pattern:
- A Protocol interface
- An InMemory implementation with RLock
- A global singleton with configure/set_for_tests/health helpers

This module provides a StoreConfigMixin for the implementation pattern
and a StoreManager descriptor for the global+configure+set+health pattern.
"""

from __future__ import annotations

import threading
from typing import Any, Generic, Protocol, TypeVar


class _StoreProtocol(Protocol):
    """Minimal store interface: every store has a name and reset."""
    backend_name: str
    shared_across_processes: bool
    def reset(self) -> None: ...


T = TypeVar("T", bound=_StoreProtocol)


class StoreConfigMixin:
    """Mixin for store implementations: provides _lock and backend metadata."""

    backend_name: str = "memory"
    shared_across_processes: bool = False

    def __init__(self) -> None:
        self._lock = threading.RLock()


class StoreManager(Generic[T]):
    """Manages a global store singleton with configure/set/health pattern.

    Usage:
        task_manager = StoreManager[DeviceTaskStore](InMemoryDeviceTaskStore)
        task_manager.configure(...)  # env-based config
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
