"""Tests for M28: tool gateway adapter, audit, and runtime wiring."""

from agent_runtime.approval import ApprovalGate
from agent_runtime.audit_trail import AuditTrail
from agent_runtime.contract import AgentStep, AgentTask, StepKind
from agent_runtime.executor import AgentRuntime
from agent_runtime.tool_exec import FakeToolExecutor, NoopToolExecutor, ShellBlockedExecutor
from agent_runtime.tool_gateway_adapter import (
    ToolExecutionDecision,
    ToolExecutionGateway,
    ToolExecutionRequest,
    build_default_gateway,
)


def test_gateway_default_noop_does_not_execute():
    gw = build_default_gateway()
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="rm -rf /")
    result = gw.execute(step)
    assert result.blocked is True
    assert "dry_run" in result.blocked_reason.lower()


def test_gateway_with_approval_allows_noop_simulation():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo hi")
    gate.check_step(step)
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate)
    result = gw.execute(step)
    assert result.ok is True
    assert result.blocked is False
    assert "noop" in result.output.lower()


def test_gateway_policy_blocks_dangerous_allowed_tools_after_approval():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(
        step_id="s1",
        kind=StepKind.SHELL_COMMAND,
        command="echo hi",
        allowed_tools=["sudo"],
    )
    gate.check_step(step)
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate)
    result = gw.execute(step)
    assert result.blocked is True
    assert "dangerous authority" in result.blocked_reason.lower()


def test_gateway_fake_executor_returns_deterministic():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo hello")
    gate.check_step(step)
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate, executor=FakeToolExecutor())
    result = gw.execute(step)
    assert result.ok is True
    assert result.blocked is False
    assert "fake" in result.evidence[0] or "echo" in result.output.lower()


def test_gateway_shell_executor_still_blocks_after_approval():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo hello")
    gate.check_step(step)
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate, executor=ShellBlockedExecutor())
    result = gw.execute(step)
    assert result.ok is False
    assert result.blocked is True
    assert "blocked" in result.blocked_reason.lower()


def test_gateway_audit_writes_events(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, command="pytest")
    gate.check_step(step, task_id="task-1", worker_id="worker-1")
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate)
    gw.execute(step, task_id="task-1", worker_id="worker-1")
    trail = AuditTrail(str(tmp_path / "audit.jsonl"))
    counts = trail.count_by_event()
    assert counts["tool_request_received"] == 1
    assert counts["tool_executor_selected"] == 1
    assert counts["tool_execution_result"] == 1
    assert trail.query(task_id="task-1")[0].worker_id == "worker-1"


def test_gateway_audit_failure_does_not_block(monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", "Z:/missing/path/audit.jsonl")
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo")
    gate.check_step(step)
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate)
    result = gw.execute(step)
    assert result.ok is True


def test_runtime_with_gateway_routes_shell():
    gw = build_default_gateway()
    rt = AgentRuntime(tool_gateway=gw)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo")
    result = rt.run_step(step)
    assert result.blocked is True


def test_runtime_with_gateway_routes_run_tests():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.RUN_TESTS, command="pytest")
    gate.check_step(step, task_id="t1")
    gate.approve(gate.get_pending()[0].approval_id)
    gw = ToolExecutionGateway(approval_gate=gate, executor=NoopToolExecutor())
    rt = AgentRuntime(tool_gateway=gw)
    result = rt.run_step(step, task_id="t1")
    assert result.ok is True
    assert "noop" in result.output.lower()


def test_runtime_without_gateway_shell_blocked():
    rt = AgentRuntime()
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo")
    result = rt.run_step(step)
    assert result.blocked is True
    assert "shell_command" in result.blocked_reason.lower()


def test_runtime_with_gateway_http_blocked():
    gw = build_default_gateway()
    rt = AgentRuntime(tool_gateway=gw)
    step = AgentStep(step_id="s1", kind=StepKind.HTTP_CALL, command="https://x")
    result = rt.run_step(step)
    assert result.blocked is True


def test_runtime_gateway_full_run_blocks_unapproved_shell():
    gate = ApprovalGate(dry_run=False)
    gw = ToolExecutionGateway(approval_gate=gate, executor=NoopToolExecutor())
    rt = AgentRuntime(tool_gateway=gw)
    task = AgentTask(task_id="t1", goal="echo hello", allowed_tools=["shell_command"])
    result = rt.run(task)
    shell_results = [step for step in result.steps if step.blocked]
    assert len(shell_results) >= 1


def test_runtime_gateway_allows_safe_steps():
    gw = build_default_gateway()
    rt = AgentRuntime(tool_gateway=gw)
    step = AgentStep(step_id="s1", kind=StepKind.SUMMARIZE, goal="test")
    result = rt.run_step(step)
    assert result.ok is True
    assert not result.blocked


def test_gateway_audit_events_have_correct_types(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=False)
    gw = ToolExecutionGateway(approval_gate=gate)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command="echo")
    gw.execute(step, task_id="t1", worker_id="w1")
    trail = AuditTrail(str(tmp_path / "audit.jsonl"))
    counts = trail.count_by_event()
    assert "tool_approval_blocked" in counts


def test_gateway_audit_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gw = build_default_gateway()
    step = AgentStep(
        step_id="api_key=sk-secret",
        kind=StepKind.SHELL_COMMAND,
        command="curl -H 'Authorization: Bearer secret12345678901234567890' http://x",
    )
    gw.execute(step, task_id="t1")
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "Bearer secret" not in raw
    assert "api_key" not in raw


def test_tool_execution_decision_defaults():
    decision = ToolExecutionDecision(allowed=False)
    assert decision.allowed is False
    assert decision.blocked_reason == ""
    assert decision.executor is None


def test_tool_execution_request_defaults():
    step = AgentStep(step_id="s1", kind=StepKind.NOOP)
    request = ToolExecutionRequest(step=step)
    assert request.step.step_id == "s1"
    assert request.task_id == ""
