"""Device gateway health payload helpers."""

from __future__ import annotations

from typing import Any

from device_gateway.auth import token_configured
from device_gateway.notifier import notifier_health
from device_gateway.protocol import PROTOCOL_VERSION
from device_gateway.sessions import registry
from device_gateway.store import task_store_health
from device_gateway.tasks import pending_count
from device_ledger.store import ledger_store_health
from device_memory.store import memory_store_health
from runtime_env import is_production_runtime


def build_device_gateway_health() -> tuple[dict[str, Any], bool]:
    task_store = task_store_health()
    session_bus = notifier_health()
    production = is_production_runtime()
    production_ready = not production or (
        bool(task_store.get("shared_across_processes")) and bool(session_bus.get("shared_across_processes"))
    )
    return (
        {
            "status": "ok" if production_ready else "degraded",
            "protocol": PROTOCOL_VERSION,
            "active_sessions": registry.count(),
            "pending_tasks": pending_count(),
            "task_store": task_store,
            "memory_store": memory_store_health(),
            "ledger_store": ledger_store_health(),
            "session_bus": session_bus,
            "auth_configured": token_configured(),
            "production_ready": production_ready,
        },
        production_ready,
    )
