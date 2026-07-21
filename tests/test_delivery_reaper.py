"""M2 delivery reaper start/stop and zombie eviction smoke."""

from __future__ import annotations

import time

import pytest

from device_gateway.delivery_reaper import start_delivery_reapers, stop_delivery_reapers
from device_gateway.sessions import DeviceSession, registry


@pytest.mark.asyncio
async def test_reaper_start_stop():
    await start_delivery_reapers()
    await start_delivery_reapers()  # idempotent
    await stop_delivery_reapers()
    await stop_delivery_reapers()


def test_zombie_session_requeue_inflight():
    registry.clear()
    from device_gateway.tasks import install_task_store_for_tests, pending_count

    install_task_store_for_tests()

    class _Ws:
        async def close(self):
            return None

        async def send_json(self, _payload):
            return None

    session = DeviceSession(device_id="dev-z", websocket=_Ws())
    task = {
        "type": "motion_task",
        "task_id": "task-zombie-1",
        "device_id": "dev-z",
        "capability": "home",
        "params": {},
    }
    from device_gateway.store import task_store

    task_store.create_task_state(task, status="dispatched")
    session.mark_task_dispatched(task)
    registry.register(session)
    # register() refreshes last_seen_at — age after register
    session.last_seen_at = time.monotonic() - 1000

    removed = registry.remove_zombies(timeout_seconds=90.0)
    assert len(removed) == 1
    assert registry.get("dev-z") is None
    # inflight requeued to pending
    assert pending_count("dev-z") >= 1
