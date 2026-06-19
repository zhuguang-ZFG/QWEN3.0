from device_gateway.sessions import DeviceSession, registry
from device_gateway.tasks import (
    create_task_from_transcript,
    enqueue_pending_task,
    pop_pending_tasks,
    task_snapshot,
)
from routes.device_gateway import (
    _dispatch_task_to_session,
    _drain_pending_tasks,
    _notify_local_session_task_available,
)


class _FailingWebSocket:
    async def send_json(self, payload):
        raise RuntimeError("send failed")


class _FailAfterWebSocket:
    def __init__(self, fail_after: int):
        self.fail_after = fail_after
        self.sent = []

    async def send_json(self, payload):
        if len(self.sent) >= self.fail_after:
            raise RuntimeError("send failed")
        self.sent.append(payload)


async def test_dispatch_task_requeues_existing_inflight_and_current_task_on_send_failure():
    websocket = _FailAfterWebSocket(fail_after=0)
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    previous = create_task_from_transcript("dev-1", "previous")
    current = create_task_from_transcript("dev-1", "current")
    session.mark_task_dispatched(previous)
    registry.register(session)

    assert await _dispatch_task_to_session(session, current) is False

    redelivered = pop_pending_tasks("dev-1", limit=10)
    assert [task["task_id"] for task in redelivered] == [previous["task_id"], current["task_id"]]
    assert registry.get("dev-1") is None


async def test_hello_pending_drain_failure_requeues_inflight_prefix_and_unsent_suffix():
    tasks = [create_task_from_transcript("dev-1", f"write {index}") for index in range(3)]
    for task in tasks:
        enqueue_pending_task("dev-1", task)
    websocket = _FailAfterWebSocket(fail_after=1)
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    registry.register(session)

    assert await _drain_pending_tasks(session) is False

    redelivered = pop_pending_tasks("dev-1", limit=10)
    assert [task["task_id"] for task in redelivered] == [task["task_id"] for task in tasks]
    assert registry.get("dev-1") is None


async def test_task_available_notification_drains_shared_queue_to_local_session():
    task = create_task_from_transcript("dev-1", "remote queued task")
    enqueue_pending_task("dev-1", task)
    websocket = _FailAfterWebSocket(fail_after=99)
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    registry.register(session)

    await _notify_local_session_task_available("dev-1")

    assert [payload["task_id"] for payload in websocket.sent] == [task["task_id"]]
    assert task_snapshot(task["task_id"])["status"] == "dispatched"
