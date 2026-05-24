"""Tests for M19 agent run orchestrator queue, leases, retry, and recovery."""

import time

from agent_runtime import (
    AgentRunLease,
    AgentRunQueue,
    AgentRunRequest,
    QueueStatus,
)
from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    AgentTask,
    StepResult,
)
from agent_runtime.store import InMemoryAgentRunStore


def test_request_defaults():
    req = AgentRunRequest(task_id="t1", goal="test")

    assert len(req.request_id) == 12
    assert req.status == QueueStatus.PENDING
    assert req.priority == 0


def test_request_copies_task_identity():
    task = AgentTask(task_id="t1", goal="review")

    req = AgentRunRequest(task=task)

    assert req.task_id == "t1"
    assert req.goal == "review"


def test_lease_expiry():
    lease = AgentRunLease(request_id="r1", worker_id="w1", lease_sec=0.001)
    time.sleep(0.01)
    assert lease.is_expired is True

    lease2 = AgentRunLease(request_id="r2", worker_id="w1", lease_sec=300)
    assert lease2.is_expired is False


def test_submit_and_list():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="review code"))

    pending = queue.list_pending()

    assert req.request_id is not None
    assert [item.request_id for item in pending] == [req.request_id]


def test_list_requests_sorts_by_priority_then_age():
    queue = AgentRunQueue()
    low = queue.submit(AgentTask(task_id="low", goal="a"))
    high = queue.submit(AgentTask(task_id="high", goal="b"))
    low.priority = 1
    high.priority = 5

    listed = queue.list_requests()

    assert listed[0].request_id == high.request_id


def test_claim_idempotent():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="test"))

    lease1 = queue.claim(req.request_id, "worker-1")
    lease2 = queue.claim(req.request_id, "worker-2")

    assert lease1 is not None
    assert lease2 is None


def test_claim_expired_lease_allows_new_claim_without_manual_expire():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    queue.claim(req.request_id, "worker-1", lease_sec=0.001)
    time.sleep(0.01)

    lease2 = queue.claim(req.request_id, "worker-2")

    assert lease2 is not None
    assert lease2.worker_id == "worker-2"


def test_finish_completed_updates_queue_and_store_task():
    store = InMemoryAgentRunStore()
    queue = AgentRunQueue(store=store)
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    result = AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED)

    assert queue.finish(req.request_id, result) is True

    assert queue.list_requests(status="completed")[0].request_id == req.request_id
    assert store.get_task("t1").status == AgentRunStatus.COMPLETED
    assert store.get_result("t1").status == AgentRunStatus.COMPLETED


def test_finish_blocked_updates_task_waiting_approval():
    store = InMemoryAgentRunStore()
    queue = AgentRunQueue(store=store)
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    result = AgentRunResult(
        task_id="t1",
        status=AgentRunStatus.COMPLETED,
        steps=[StepResult(step_id="s1", ok=False, blocked=True)],
    )

    assert queue.finish(req.request_id, result) is True

    assert queue.list_requests(status="blocked")[0].request_id == req.request_id
    assert store.get_task("t1").status == AgentRunStatus.WAITING_APPROVAL


def test_finish_rejects_mismatched_result_task_id():
    store = InMemoryAgentRunStore()
    queue = AgentRunQueue(store=store)
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    result = AgentRunResult(task_id="other", status=AgentRunStatus.COMPLETED)

    assert queue.finish(req.request_id, result) is False
    assert queue.list_pending()[0].request_id == req.request_id
    assert store.get_result("other") is None


def test_finish_does_not_overwrite_terminal_result():
    store = InMemoryAgentRunStore()
    queue = AgentRunQueue(store=store)
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    completed = AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED)
    failed = AgentRunResult(task_id="t1", status=AgentRunStatus.FAILED)

    assert queue.finish(req.request_id, completed) is True
    assert queue.finish(req.request_id, failed) is False

    assert queue.list_requests(status="completed")[0].request_id == req.request_id
    assert store.get_result("t1").status == AgentRunStatus.COMPLETED


def test_finish_nonexistent():
    queue = AgentRunQueue()
    result = AgentRunResult(task_id="ghost", status=AgentRunStatus.COMPLETED)

    assert queue.finish("nonexistent", result) is False


def test_retry_failed_resets_queue_and_store_task():
    store = InMemoryAgentRunStore()
    queue = AgentRunQueue(store=store)
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    queue.finish(req.request_id, AgentRunResult(task_id="t1", status=AgentRunStatus.FAILED))

    retried = queue.retry(req.request_id)

    assert retried is not None
    assert queue.list_pending()[0].request_id == req.request_id
    assert store.get_task("t1").status == AgentRunStatus.PENDING


def test_retry_completed_rejected():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    queue.finish(req.request_id, AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED))

    assert queue.retry(req.request_id) is None


def test_run_one_from_pending():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="review the code"))

    result = queue.run_one(req.request_id)

    assert result is not None
    assert result.ok is True
    assert queue.list_requests(status="completed")[0].request_id == req.request_id
    assert queue.stats()["active_leases"] == 0


def test_run_one_refuses_terminal_request():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="review the code"))
    queue.finish(req.request_id, AgentRunResult(task_id="t1", status=AgentRunStatus.COMPLETED))

    assert queue.run_one(req.request_id) is None


def test_run_one_refuses_expired_claimed_request():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="review the code"))
    queue.claim(req.request_id, "worker-1", lease_sec=0.001)
    time.sleep(0.01)

    assert queue.run_one(req.request_id) is None
    assert queue.list_pending()[0].request_id == req.request_id


def test_expire_leases_releases_pending():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(task_id="t1", goal="test"))
    queue.claim(req.request_id, "w1", lease_sec=0.001)
    time.sleep(0.01)

    expired = queue.expire_leases()

    assert expired == 1
    assert queue.list_pending()[0].request_id == req.request_id


def test_list_requests_by_status():
    queue = AgentRunQueue()
    queue.submit(AgentTask(task_id="t1", goal="a"))
    req2 = queue.submit(AgentTask(task_id="t2", goal="b"))
    queue.finish(req2.request_id, AgentRunResult(task_id="t2", status=AgentRunStatus.COMPLETED))

    assert len(queue.list_requests(status="pending")) == 1
    assert len(queue.list_requests(status="completed")) == 1


def test_stats():
    queue = AgentRunQueue()
    queue.submit(AgentTask(task_id="t1", goal="a"))
    req = queue.submit(AgentTask(task_id="t2", goal="b"))
    queue.claim(req.request_id, "w1")

    stats = queue.stats()

    assert stats["total"] == 2
    assert stats["active_leases"] == 1
    assert stats["by_status"]["claimed"] == 1


def test_store_integration():
    store = InMemoryAgentRunStore()
    queue = AgentRunQueue(store=store)
    req = queue.submit(AgentTask(task_id="store-q", goal="review"))

    result = AgentRunResult(task_id="store-q", status=AgentRunStatus.COMPLETED)
    queue.finish(req.request_id, result)

    assert store.get_task("store-q").status == AgentRunStatus.COMPLETED
    assert store.get_result("store-q") is not None


def test_recover_from_store_loads_only_unfinished_tasks():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(
        task_id="orphan-1",
        goal="lost task",
        status=AgentRunStatus.PENDING,
    ))
    store.save_task(AgentTask(
        task_id="orphan-2",
        goal="done task",
        status=AgentRunStatus.COMPLETED,
    ))
    store.save_task(AgentTask(
        task_id="orphan-3",
        goal="failed task",
        status=AgentRunStatus.FAILED,
    ))

    queue = AgentRunQueue(store=store)
    recovered = queue.recover_from_store()
    task_ids = {req.task_id for req in queue.list_requests()}

    assert recovered == 1
    assert task_ids == {"orphan-1"}


def test_recover_from_store_skips_task_with_completed_result_even_if_task_stale():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(
        task_id="stale",
        goal="was completed",
        status=AgentRunStatus.PENDING,
    ))
    store.save_result(AgentRunResult(
        task_id="stale",
        status=AgentRunStatus.COMPLETED,
    ))

    queue = AgentRunQueue(store=store)

    assert queue.recover_from_store() == 0
    assert queue.list_requests() == []


def test_recover_from_store_skips_blocked_result():
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(
        task_id="blocked",
        goal="deploy",
        status=AgentRunStatus.PENDING,
    ))
    store.save_result(AgentRunResult(
        task_id="blocked",
        status=AgentRunStatus.COMPLETED,
        steps=[StepResult(step_id="s1", ok=False, blocked=True)],
    ))

    queue = AgentRunQueue(store=store)

    assert queue.recover_from_store() == 0


def test_blocked_task_not_auto_retried():
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(
        task_id="t1",
        goal="deploy",
        allowed_tools=["shell"],
    ))

    queue.run_one(req.request_id)

    assert queue.list_requests(status="blocked")[0].request_id == req.request_id
    assert queue.run_one(req.request_id) is None
    assert queue.retry(req.request_id) is not None
    queue.run_one(req.request_id)
    assert queue.list_requests(status="blocked")[0].request_id == req.request_id


def test_event_bridge_never_raises(monkeypatch):
    import agent_runtime.orchestrator as orchestrator

    def boom(*args, **kwargs):
        raise RuntimeError("event sink down")

    monkeypatch.setattr(orchestrator, "redact_value", boom)
    queue = AgentRunQueue()

    req = queue.submit(AgentTask(task_id="t1", goal="review"))
    assert req is not None  # should not crash even when event sink fails


def test_save_and_load_state_preserves_requests(tmp_path, monkeypatch):
    state_path = tmp_path / "q_state.jsonl"
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(state_path))
    q1 = AgentRunQueue()
    q1.submit(AgentTask(task_id="t1", goal="review"))

    assert q1.save_state() is True
    assert state_path.exists()

    q2 = AgentRunQueue(store=q1.store)
    loaded = q2.load_state()

    assert loaded == 1
    assert [req.task_id for req in q2.list_pending()] == ["t1"]


def test_save_and_load_state_preserves_leases(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q1 = AgentRunQueue()
    req = q1.submit(AgentTask(task_id="t1", goal="test"))
    q1.claim(req.request_id, "worker-1")
    q1.save_state()

    q2 = AgentRunQueue(store=q1.store)
    q2.load_state()

    assert q2.stats()["active_leases"] == 1


def test_lease_survives_save_load_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q1 = AgentRunQueue()
    req = q1.submit(AgentTask(task_id="t1", goal="test"))
    q1.claim(req.request_id, "worker-1", lease_sec=300)
    q1.save_state()

    q2 = AgentRunQueue(store=q1.store)
    q2.load_state()
    lease2 = q2.claim(req.request_id, "worker-2")

    assert lease2 is None


def test_expired_lease_after_load_allows_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q1 = AgentRunQueue()
    req = q1.submit(AgentTask(task_id="t1", goal="test"))
    # Short lease that will expire
    req_id = req.request_id
    q1._leases[req_id] = AgentRunLease(request_id=req_id, worker_id="w1", lease_sec=0.001)
    q1._requests[req_id].status = QueueStatus.CLAIMED
    q1.save_state()
    time.sleep(0.01)

    q2 = AgentRunQueue(store=q1.store)
    q2.load_state()
    lease = q2.claim(req_id, "worker-2")
    assert lease is not None


def test_save_and_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q = AgentRunQueue()
    q.submit(AgentTask(task_id="t1", goal="test"))
    snap = q.save_and_snapshot()
    assert snap["total"] == 1


def test_clear_state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q = AgentRunQueue()
    q.submit(AgentTask(task_id="t1", goal="test"))
    q.save_state()
    assert (tmp_path / "q_state.jsonl").exists()
    q.clear_state_file()

    assert not (tmp_path / "q_state.jsonl").exists()

    q2 = AgentRunQueue(store=q.store)
    assert q2.load_state() == 1
    assert [req.task_id for req in q2.list_pending()] == ["t1"]


def test_load_state_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q1 = AgentRunQueue()
    q1.submit(AgentTask(task_id="t1", goal="test"))
    q1.save_state()

    q2 = AgentRunQueue(store=q1.store)
    first = q2.load_state()
    second = q2.load_state()

    assert first == 1
    assert second == 0
    assert q2.stats()["total"] == 1


def test_full_cycle_save_run_recover(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "q_state.jsonl"))
    q1 = AgentRunQueue()
    req = q1.submit(AgentTask(task_id="t1", goal="review the code"))
    q1.run_one(req.request_id)
    q1.save_state()

    q2 = AgentRunQueue(store=q1.store)
    q2.load_state()
    # Task should be completed, not re-queued
    assert len(q2.list_pending()) == 0
    result = q2.store.get_result("t1")
    assert result is not None
    assert result.ok is True

    assert req.task_id == "t1"


def test_save_state_redacts_secret_like_fields(tmp_path, monkeypatch):
    state_path = tmp_path / "q_state.jsonl"
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(state_path))
    queue = AgentRunQueue()
    req = queue.submit(AgentTask(
        task_id="task-1",
        goal="use api_key=sk-secret",
    ))
    queue.claim(req.request_id, "worker-token=secret")

    assert queue.save_state() is True
    raw = state_path.read_text(encoding="utf-8")

    assert "api_key" not in raw
    assert "sk-secret" not in raw
    assert "worker-token=secret" not in raw
    assert "[REDACTED]" in raw


def test_load_state_ignores_bad_lines_and_bad_numbers(tmp_path, monkeypatch):
    state_path = tmp_path / "q_state.jsonl"
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(state_path))
    state_path.write_text(
        "\n".join([
            "not json",
            '{"_type":"queue_request","request_id":"r1","task_id":"t1",'
            '"goal":"ok","priority":"bad","created_at":"bad","status":"bad"}',
            "[]",
        ]),
        encoding="utf-8",
    )

    queue = AgentRunQueue()
    loaded = queue.load_state()
    req = queue.list_pending()[0]

    assert loaded == 1
    assert req.request_id == "r1"
    assert req.priority == 0
    assert req.created_at == 0.0


def test_claimed_state_without_valid_lease_restores_pending(tmp_path, monkeypatch):
    state_path = tmp_path / "q_state.jsonl"
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(state_path))
    state_path.write_text(
        '{"_type":"queue_request","request_id":"r1","task_id":"t1",'
        '"goal":"ok","priority":0,"created_at":1,"status":"claimed"}\n',
        encoding="utf-8",
    )

    queue = AgentRunQueue()

    assert queue.load_state() == 1
    assert queue.list_pending()[0].request_id == "r1"


def test_save_state_supports_filename_without_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIMA_QUEUE_STATE", "queue_state.jsonl")
    queue = AgentRunQueue()
    queue.submit(AgentTask(task_id="t1", goal="test"))

    assert queue.save_state() is True
    assert (tmp_path / "queue_state.jsonl").exists()


def test_load_state_without_file_recovers_pending_store_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_QUEUE_STATE", str(tmp_path / "missing.jsonl"))
    store = InMemoryAgentRunStore()
    store.save_task(AgentTask(
        task_id="orphan",
        goal="recover me",
        status=AgentRunStatus.PENDING,
    ))
    queue = AgentRunQueue(store=store)

    assert queue.load_state() == 1
    assert [req.task_id for req in queue.list_pending()] == ["orphan"]
