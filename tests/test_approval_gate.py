"""Tests for M22 approval gate behavior and safety boundaries."""

import time

from agent_runtime import ApprovalGate, ApprovalRequest, ApprovalStatus
from agent_runtime.approval import DANGEROUS_KINDS, REQUIRES_APPROVAL_KINDS
from agent_runtime.contract import AgentStep, StepKind


def test_approval_request_defaults():
    req = ApprovalRequest(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="deploy")

    assert len(req.approval_id) == 12
    assert req.status == ApprovalStatus.PENDING
    assert req.is_expired is False


def test_approval_request_expiry():
    req = ApprovalRequest(step_id="s1", kind=StepKind.NOOP, ttl_sec=0.001)
    time.sleep(0.01)

    assert req.is_expired is True


def test_approval_request_to_dict_redacts_secrets():
    req = ApprovalRequest(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        task_id="t1",
        worker_id="worker-token=secret",
        goal="use api_key=sk-secret",
        command="echo Bearer secret",
        reason="token=secret",
    )

    data = req.to_dict()

    assert data["kind"] == "shell_command"
    assert data["task_id"] == "t1"
    assert data["worker_id"] == "[REDACTED]"
    assert data["goal"] == "[REDACTED]"
    assert data["command"] == "[REDACTED]"
    assert data["reason"] == "[REDACTED]"


def test_request_matches_exact_authority_surface():
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        command="echo hi",
    )
    req = ApprovalRequest(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        task_id="t1",
        worker_id="w1",
        command="echo hi",
    )

    assert req.matches(step, task_id="t1", worker_id="w1") is True
    assert req.matches(step, task_id="other", worker_id="w1") is False
    assert req.matches(AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        command="rm -rf tmp",
    ), task_id="t1", worker_id="w1") is False


def test_dry_run_blocks_shell_without_request():
    gate = ApprovalGate(dry_run=True)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="deploy")

    result = gate.check_step(step)

    assert result is not None
    assert result.blocked is True
    assert "dry_run" in result.blocked_reason.lower()
    assert gate.get_pending() == []


def test_dry_run_allows_summarize():
    gate = ApprovalGate(dry_run=True)
    step = AgentStep(step_id="s1", kind=StepKind.SUMMARIZE, goal="summarize")

    assert gate.check_step(step) is None


def test_dry_run_does_not_block_run_tests():
    gate = ApprovalGate(dry_run=True)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, goal="run tests")

    assert gate.check_step(step) is None


def test_non_dry_run_requests_approval():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        goal="deploy",
        command="echo hi",
    )

    result = gate.check_step(step, task_id="t1", worker_id="w1")
    pending = gate.get_pending()

    assert result is not None
    assert result.blocked is True
    assert "approval required" in result.blocked_reason.lower()
    assert len(pending) == 1
    assert pending[0].command == "echo hi"


def test_repeated_pending_check_reuses_request():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND)

    gate.check_step(step, task_id="t1", worker_id="w1")
    gate.check_step(step, task_id="t1", worker_id="w1")

    assert len(gate.get_pending()) == 1
    assert gate.stats()["total"] == 1


def test_approve_granted_allows_same_step_surface():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        goal="test",
        command="echo hi",
    )
    gate.check_step(step, task_id="t1", worker_id="w1")
    pending = gate.get_pending()

    assert gate.approve(pending[0].approval_id) is True

    assert gate.check_step(step, task_id="t1", worker_id="w1") is None


def test_approved_step_does_not_allow_different_task_worker_or_command():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        command="echo hi",
    )
    gate.check_step(step, task_id="t1", worker_id="w1")
    approval_id = gate.get_pending()[0].approval_id
    gate.approve(approval_id)

    different_command = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        command="echo bye",
    )

    assert gate.check_step(step, task_id="t2", worker_id="w1").blocked is True
    assert gate.check_step(step, task_id="t1", worker_id="w2").blocked is True
    assert gate.check_step(
        different_command,
        task_id="t1",
        worker_id="w1",
    ).blocked is True


def test_deny_blocks_without_creating_new_request():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test")
    gate.check_step(step)
    pending = gate.get_pending()

    assert gate.deny(pending[0].approval_id) is True

    result = gate.check_step(step)

    assert result is not None
    assert result.blocked is True
    assert "denied" in result.blocked_reason
    assert gate.get_pending() == []
    assert gate.stats()["total"] == 1


def test_approve_denied_fails():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test")
    gate.check_step(step)
    approval_id = gate.get_pending()[0].approval_id
    gate.deny(approval_id)

    assert gate.approve(approval_id) is False


def test_approve_expired_fails_and_marks_expired():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test")
    gate.check_step(step)
    approval_id = gate.get_pending()[0].approval_id
    gate._requests[approval_id].expires_at = time.time() - 1

    assert gate.approve(approval_id) is False
    assert gate.get_request(approval_id).status == ApprovalStatus.EXPIRED


def test_approve_nonexistent():
    gate = ApprovalGate()

    assert gate.approve("nonexistent") is False


def test_deny_approved_fails():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND)
    gate.check_step(step)
    approval_id = gate.get_pending()[0].approval_id
    gate.approve(approval_id)

    assert gate.deny(approval_id) is False


def test_run_tests_requires_approval_non_dry():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, goal="run tests")

    result = gate.check_step(step)

    assert result is not None
    assert result.blocked is True


def test_expire_stale():
    gate = ApprovalGate(dry_run=False)
    gate.request_approval(AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        goal="test",
    ))
    for req in gate._requests.values():
        req.expires_at = time.time() - 1

    expired = gate.expire_stale()

    assert expired == 1


def test_expired_pending_check_marks_expired_and_does_not_duplicate():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND)
    gate.check_step(step)
    approval_id = gate.get_pending()[0].approval_id
    gate._requests[approval_id].expires_at = time.time() - 1

    result = gate.check_step(step)

    assert result is not None
    assert result.blocked is True
    assert "expired" in result.blocked_reason
    assert gate.stats()["total"] == 1


def test_approval_stats():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test")

    gate.check_step(step)
    stats = gate.stats()

    assert stats["total"] == 1
    assert stats["by_status"].get("pending", 0) == 1


def test_audit_redacts_and_never_raises(monkeypatch):
    import agent_runtime.approval as approval

    def boom(*args, **kwargs):
        raise RuntimeError("event sink down")

    monkeypatch.setattr(approval, "redact", boom)
    gate = ApprovalGate(dry_run=False)

    request = gate.request_approval(AgentStep(
        step_id="token=secret",
        kind=StepKind.SHELL_COMMAND,
    ))

    assert request.status == ApprovalStatus.PENDING


def test_dangerous_kinds():
    assert StepKind.SHELL_COMMAND in DANGEROUS_KINDS
    assert StepKind.SUMMARIZE not in DANGEROUS_KINDS
    assert StepKind.RETRIEVE_CONTEXT not in DANGEROUS_KINDS


def test_requires_approval_kinds():
    assert StepKind.SHELL_COMMAND in REQUIRES_APPROVAL_KINDS
    assert StepKind.RUN_TESTS in REQUIRES_APPROVAL_KINDS
    assert StepKind.SUMMARIZE not in REQUIRES_APPROVAL_KINDS
