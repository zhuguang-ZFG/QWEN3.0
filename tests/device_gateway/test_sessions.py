"""Tests for device_gateway.sessions."""

import time
from unittest.mock import AsyncMock

from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import install_task_store_for_tests, pending_count
from routes.device_gateway_helpers import _reset_for_tests


def test_registry_remove_zombies_requeues_outstanding_tasks():
    """Stale sessions without recent heartbeats are evicted and their in-flight tasks requeued."""
    _reset_for_tests()
    install_task_store_for_tests()

    websocket = AsyncMock()
    session = DeviceSession(device_id="dev-zombie", websocket=websocket)
    registry.register(session)

    task = {
        "task_id": "task-1",
        "device_id": "dev-zombie",
        "capability": "draw_svg",
        "params": {},
    }
    session.mark_task_dispatched(task)

    # Simulate a heartbeat that stopped a long time ago.
    session.last_seen_at = time.monotonic() - 300

    removed = registry.remove_zombies(timeout_seconds=60)

    assert len(removed) == 1
    assert removed[0].device_id == "dev-zombie"
    assert registry.get("dev-zombie") is None
    assert pending_count("dev-zombie") == 1
