"""Device Gateway task-store abstraction.

The default store is in-memory for local development and tests. The interface is
kept explicit so Redis/Postgres-backed stores can replace it for multi-process
or multi-node deployments without rewriting route logic.
"""

from __future__ import annotations

from typing import Any, Protocol

from device_gateway.store_utils import StoreManager


class DeviceTaskStore(Protocol):
    backend_name: str
    shared_across_processes: bool

    def reset(self) -> None: ...

    def ping(self) -> None: ...

    def close(self) -> None: ...

    def next_task_id(self) -> str: ...

    def create_task_state(self, task: dict[str, Any], status: str = "created") -> None: ...

    def record_motion_event(self, event: dict[str, Any]) -> dict[str, Any]: ...

    def task_snapshot(self, task_id: str) -> dict[str, Any] | None: ...

    def active_tasks_for_device(self, device_id: str) -> list[dict[str, Any]]: ...

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int: ...

    def pop_pending_tasks(self, device_id: str, limit: int = 16) -> list[dict[str, Any]]: ...

    def requeue_pending_tasks(self, device_id: str, tasks: list[dict[str, Any]]) -> int: ...

    def mark_task_dispatched(self, task_id: str) -> None: ...

    def ack_processing(self, device_id: str, task_id: str) -> bool: ...

    def recover_stale_processing(self, device_id: str, timeout_sec: float = 120.0) -> int: ...

    def pending_count(self, device_id: str | None = None) -> int: ...

    def list_tasks_for_device(self, device_id: str, status: str = "", limit: int = 20) -> list[dict[str, Any]]: ...

    def list_inflight_task_ids(self, limit: int = 1000) -> list[str]: ...

    def increment_retry_count(self, task_id: str) -> int: ...

    def reset_task_for_retry(self, task_id: str) -> None: ...

    def remove_pending_task(self, device_id: str, task_id: str) -> bool: ...

    def abandon_processing_task(self, device_id: str, task_id: str) -> bool: ...


from device_gateway.memory_store import InMemoryDeviceTaskStore


task_manager: StoreManager[DeviceTaskStore] = StoreManager[DeviceTaskStore](InMemoryDeviceTaskStore)
task_store: DeviceTaskStore = task_manager.store


def task_store_health() -> dict[str, Any]:
    return task_manager.health()


def set_task_store_for_tests(store: DeviceTaskStore) -> None:
    global task_store
    task_manager.set(store)
    task_store = task_manager.store


def configure_task_store_from_env() -> None:
    global task_store
    from config.db_config import DEVICE_REDIS_URL

    from .redis_store import RedisDeviceTaskStore

    task_manager.configure_from_env(
        "LIMA_DEVICE_TASK_STORE",
        DEVICE_REDIS_URL,
        RedisDeviceTaskStore,
        use_redis_when_url_present=True,
    )
    task_store = task_manager.store
