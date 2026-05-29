"""Tests for M24-M27: Tool exec, audit trail, operator CLI, E2E release gate."""

import json

from agent_runtime import ToolResult
from agent_runtime.approval import ApprovalGate
from agent_runtime.audit_trail import AuditTrail, audit_event
from agent_runtime.cli import (
    approve,
    deny_approval,
    list_pending_approvals,
    quarantine_worker,
    queue_summary,
    retry_task,
    status_snapshot,
    status_snapshot_json,
    worker_summary,
)
from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    AgentStep,
    AgentTask,
    StepKind,
)
from agent_runtime.executor import AgentRuntime
from agent_runtime.orchestrator import AgentRunQueue, WorkerGovernor
from agent_runtime.store import InMemoryAgentRunStore
from agent_runtime.tool_exec import (
    FakeToolExecutor,
    NoopToolExecutor,
    ShellBlockedExecutor,
    get_executor,
)


# M24: Tool executors


def test_noop_executor_never_executes():
    exc = NoopToolExecutor()
    r = exc.run("rm -rf /")
    assert r.ok is True
    assert r.executed is False
    assert "noop" in r.output


def test_fake_executor_returns_deterministic():
    exc = FakeToolExecutor()
    r = exc.run("pytest --verbose")
    assert r.ok is True
    assert "passed" in r.output
    assert r.executed is False


def test_fake_executor_unknown_command():
    exc = FakeToolExecutor()
    r = exc.run("some_unknown_cmd --flag")
    assert "Unknown command" in r.output
    assert r.executed is False


def test_shell_blocked_executor():
    exc = ShellBlockedExecutor()
    r = exc.run("echo hello")
    assert r.ok is False
    assert "blocked" in r.error
    assert r.executed is False


def test_get_executor_defaults_noop():
    exc = get_executor()
    assert isinstance(exc, NoopToolExecutor)


def test_get_executor_fake():
    exc = get_executor(fake_outputs={"echo": "hello"})
    assert isinstance(exc, FakeToolExecutor)
    assert exc.run("echo test").output == "hello"


def test_get_executor_shell_blocked():
    exc = get_executor(allow_shell=True)
    assert isinstance(exc, ShellBlockedExecutor)


def test_tool_executor_redacts_secret_commands():
    exc = NoopToolExecutor()
    r = exc.run("echo api_key=supersecretvalue1234567890")
    assert r.output == "[noop] Would execute: [REDACTED]"


def test_fake_executor_does_not_share_custom_responses():
    custom = get_executor(fake_outputs={"echo": "custom echo"})
    assert custom.run("echo test").output == "custom echo"
    fresh = FakeToolExecutor()
    assert fresh.run("echo test").output == "[fake] echo output"


def test_tool_result_exported_from_package():
    result = ToolResult(ok=True)
    assert result.ok is True


# M25: Audit trail


def test_audit_entry_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    e = audit_event("test_event", task_id="t1", worker_id="w1")
    assert e.event == "test_event"
    assert e.audit_id.startswith("audit-")


def test_audit_trail_write_and_query(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    trail = AuditTrail()
    trail.record("approval_requested", task_id="t1", approval_id="a1")
    trail.record("approval_granted", task_id="t1", approval_id="a1")
    trail.record("step_blocked", task_id="t2")

    results = trail.query(task_id="t1")
    assert len(results) == 2

    results2 = trail.query(event="step_blocked")
    assert len(results2) == 1


def test_audit_trail_count_by_event(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    trail = AuditTrail()
    trail.record("a")
    trail.record("a")
    trail.record("b")
    counts = trail.count_by_event()
    assert counts["a"] == 2
    assert counts["b"] == 1


def test_audit_trail_skips_bad_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    path = tmp_path / "audit.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write("not json\n")
        f.write(
            '{"event":"good","task_id":"","worker_id":"","request_id":"",'
            '"approval_id":"","detail":"","timestamp":0,"audit_id":"x"}\n'
        )
    trail = AuditTrail(str(path))
    results = trail.query()
    assert len(results) == 1


def test_audit_trail_redacts_secret_values(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    trail = AuditTrail()
    trail.record("approval_requested", detail="api_key=supersecretvalue1234567890")
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "supersecretvalue" not in raw
    assert "[REDACTED]" in raw


def test_global_audit_trail_tracks_env_path_changes(tmp_path, monkeypatch):
    first = tmp_path / "audit-1.jsonl"
    second = tmp_path / "audit-2.jsonl"
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(first))
    audit_event("first")
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(second))
    audit_event("second")
    assert first.exists()
    assert second.exists()


# M26: Operator CLI


def test_list_pending_approvals():
    gate = ApprovalGate(dry_run=False)
    gate.request_approval(AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test"))
    out = list_pending_approvals(gate)
    assert "s1" in out
    assert "shell_command" in out


def test_list_pending_approvals_empty():
    gate = ApprovalGate(dry_run=True)
    assert list_pending_approvals(gate) == "No pending approvals."


def test_approve_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=False)
    gate.request_approval(AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test"))
    pid = gate.get_pending()[0].approval_id
    out = approve(gate, pid)
    assert "Approved" in out


def test_deny_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=False)
    gate.request_approval(AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test"))
    pid = gate.get_pending()[0].approval_id
    out = deny_approval(gate, pid)
    assert "Denied" in out


def test_retry_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    q = AgentRunQueue()
    req = q.submit(AgentTask(task_id="t1", goal="test"))
    q.finish(req.request_id, AgentRunResult(task_id="t1", status=AgentRunStatus.FAILED))
    out = retry_task(q, req.request_id)
    assert "Retrying" in out


def test_quarantine_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    q = AgentRunQueue()
    gov = WorkerGovernor(q)
    gov.register("w1")
    out = quarantine_worker(gov, "w1")
    assert "Quarantined" in out


def test_queue_summary():
    q = AgentRunQueue()
    q.submit(AgentTask(task_id="t1", goal="test"))
    out = queue_summary(q)
    assert "pending" in out.lower()


def test_worker_summary():
    q = AgentRunQueue()
    gov = WorkerGovernor(q)
    gov.register("w1")
    gov.register("w2")
    out = worker_summary(gov)
    assert "2" in out


def test_status_snapshot():
    q = AgentRunQueue()
    q.submit(AgentTask(task_id="t1", goal="test"))
    out = status_snapshot(q, store=q.store)
    assert "Queue" in out or "pending" in out.lower()


def test_status_snapshot_json():
    q = AgentRunQueue()
    q.submit(AgentTask(task_id="t1", goal="test"))
    data = json.loads(status_snapshot_json(q))
    assert "queue" in data


# M27: E2E release gate


def test_e2e_submit_claim_approve_run_resume_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    store = InMemoryAgentRunStore()

    q = AgentRunQueue(store=store)
    req = q.submit(AgentTask(task_id="e2e-t1", goal="review the code"))
    assert req is not None

    lease = q.claim(req.request_id, "worker-1")
    assert lease is not None

    result = q.run_one(req.request_id)
    assert result is not None
    assert result.ok is True
    assert q._requests[req.request_id].status.value == "completed"

    from agent_runtime.resume import resume_task

    state = resume_task("e2e-t1", store)
    assert state is not None
    assert state.next_action == "done"

    stored_task = store.get_task("e2e-t1")
    assert stored_task is not None
    stored_result = store.get_result("e2e-t1")
    assert stored_result is not None
    assert stored_result.ok is True


def test_e2e_blocked_shell_requires_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=True)
    store = InMemoryAgentRunStore()
    rt = AgentRuntime(approval_gate=gate, store=store)
    q = AgentRunQueue(store=store, runtime=rt)

    req = q.submit(AgentTask(task_id="e2e-shell", goal="deploy", allowed_tools=["shell"]))
    result = q.run_one(req.request_id)

    shell_blocked = any(s.blocked for s in result.steps)
    assert shell_blocked is True

    stored = store.get_task("e2e-shell")
    assert stored is not None


def test_e2e_worker_quarantine_prevents_claim():
    q = AgentRunQueue()
    gov = WorkerGovernor(q)
    gov.register("w1")
    gov.quarantine("w1")

    req = q.submit(AgentTask(task_id="t1", goal="test"))
    lease = gov.claim_for_worker("w1", req.request_id)
    assert lease is None
