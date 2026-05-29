"""Tests for M34: real executor scaffold, gates, audit, and exports."""

from agent_runtime import PreflightResult, RealExecutorConfig, RealToolExecutor
from agent_runtime.contract import AgentStep, StepKind
from agent_runtime.feature_flags import ExecutionFeatureFlags
from agent_runtime.real_executor import preflight_real_execution


def _shell_config(**kwargs) -> RealExecutorConfig:
    defaults = {
        "enabled": True,
        "dry_run": False,
        "execution_kind": "shell",
        "operator_session_id": "sess-1",
        "required_audit_refs": ["audit-ref-1"],
    }
    defaults.update(kwargs)
    return RealExecutorConfig(**defaults)


def _shell_step(command: str = "pytest --tb=short") -> AgentStep:
    return AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, command=command)


def _flags(**kwargs) -> ExecutionFeatureFlags:
    defaults = {
        "dry_run": False,
        "allow_shell": True,
        "shell_allowlist": frozenset({"pytest", "echo", "python", "git"}),
    }
    defaults.update(kwargs)
    return ExecutionFeatureFlags(**defaults)


def test_default_config_blocked():
    result = preflight_real_execution(RealExecutorConfig(), _shell_step(), _flags())
    assert result.passed is False
    assert "config.enabled is False" in result.blocked_reason


def test_config_dry_run_blocked():
    result = preflight_real_execution(_shell_config(dry_run=True), _shell_step(), _flags())
    assert result.passed is False
    assert "dry_run" in result.blocked_reason.lower()


def test_flags_dry_run_blocked():
    result = preflight_real_execution(_shell_config(), _shell_step(), _flags(dry_run=True))
    assert result.passed is False
    assert "flags_dry_run" in result.blocked_reason


def test_missing_session_blocked():
    result = preflight_real_execution(
        _shell_config(operator_session_id=""),
        _shell_step(),
        _flags(),
    )
    assert result.passed is False
    assert "operator_session" in result.blocked_reason


def test_missing_audit_refs_not_blocking():
    """audit_refs are now optional ( lowered barrier for safe mode )."""
    result = preflight_real_execution(
        _shell_config(required_audit_refs=[]),
        _shell_step(),
        _flags(),
    )
    # audit_refs no longer required — should still pass
    assert result.passed is True


def test_shell_allowlist_not_matched():
    result = preflight_real_execution(_shell_config(), _shell_step("rm -rf /"), _flags())
    assert result.passed is False
    assert "shell_allowlist" in result.blocked_reason


def test_network_allowlist_blocked():
    config = _shell_config(execution_kind="network")
    flags = _flags(
        allow_network=True,
        network_domain_allowlist=frozenset({"api.example.com"}),
    )
    result = preflight_real_execution(config, _shell_step("https://x.com"), flags)
    assert result.passed is False
    assert "network_allowlist" in result.blocked_reason


def test_workspace_allowlist_blocked(tmp_path):
    config = _shell_config(execution_kind="workspace")
    flags = _flags(
        allow_workspace_write=True,
        workspace_allowlist=frozenset({str(tmp_path)}),
    )
    result = preflight_real_execution(config, _shell_step(str(tmp_path.parent / "x.py")), flags)
    assert result.passed is False
    assert "workspace_allowlist" in result.blocked_reason


def test_unknown_execution_kind_blocked():
    result = preflight_real_execution(
        _shell_config(execution_kind="database"),
        _shell_step(),
        _flags(),
    )
    assert result.passed is False
    assert "execution_kind" in result.blocked_reason


def test_all_gates_passed_shell_executes():
    config = _shell_config()
    flags = _flags()
    result = preflight_real_execution(config, _shell_step(), flags)
    assert result.passed is True

    executor = RealToolExecutor(config=config, flags=flags)
    tool_result = executor.run("echo m1-test-ok")
    assert tool_result.ok is True
    assert tool_result.executed is True
    assert "m1-test-ok" in tool_result.output


def test_network_all_gates_passed_dispatches():
    config = _shell_config(execution_kind="network")
    flags = _flags(
        allow_network=True,
        network_domain_allowlist=frozenset({"api.example.com"}),
    )
    result = preflight_real_execution(
        config,
        _shell_step("https://api.example.com/v1"),
        flags,
    )
    assert result.passed is True
    tool_result = RealToolExecutor(config=config, flags=flags).run(
        "https://api.example.com/v1"
    )
    assert tool_result.executed is True


def test_workspace_all_gates_passed_dispatches(tmp_path):
    config = _shell_config(execution_kind="workspace")
    flags = _flags(
        allow_workspace_write=True,
        workspace_allowlist=frozenset({str(tmp_path)}),
    )
    target = tmp_path / "ok.txt"
    result = preflight_real_execution(config, _shell_step(str(target)), flags)
    assert result.passed is True
    tool_result = RealToolExecutor(config=config, flags=flags).run(str(target))
    assert tool_result.executed is True
    assert tool_result.ok is True


def test_real_executor_default_preflight_blocks():
    executor = RealToolExecutor()
    result = executor.run("echo hello")
    assert result.ok is False
    assert result.executed is False
    assert executor.last_preflight is not None
    assert executor.last_preflight.passed is False


def test_preflight_writes_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    preflight_real_execution(_shell_config(), _shell_step(), _flags())
    from agent_runtime.audit_trail import AuditTrail

    records = AuditTrail(str(tmp_path / "audit.jsonl")).query()
    assert any(record.event == "real_execution_preflight" for record in records)


def test_blocked_preflight_writes_blocked_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    preflight_real_execution(RealExecutorConfig(), _shell_step(), _flags())
    from agent_runtime.audit_trail import AuditTrail

    events = {record.event for record in AuditTrail(str(tmp_path / "audit.jsonl")).query()}
    assert "real_execution_blocked" in events


def test_blocked_executor_writes_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    config = _shell_config(dry_run=True)
    executor = RealToolExecutor(config=config, flags=_flags(dry_run=True))
    executor.run("pytest")
    from agent_runtime.audit_trail import AuditTrail

    events = {record.event for record in AuditTrail(str(tmp_path / "audit.jsonl")).query()}
    assert "real_execution_blocked" in events


def test_preflight_audit_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    preflight_real_execution(
        RealExecutorConfig(),
        _shell_step("pytest --token=supersecretvalue1234567890"),
        _flags(),
    )
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "supersecretvalue" not in raw


def test_config_fields_and_preflight_exported():
    config = RealExecutorConfig()
    data = {
        field: getattr(config, field)
        for field in (
            "enabled",
            "dry_run",
            "execution_kind",
            "operator_session_id",
            "required_audit_refs",
            "allowlist_snapshot",
        )
    }
    assert data["enabled"] is False
    assert data["dry_run"] is True
    assert data["execution_kind"] == "shell"
    assert PreflightResult(passed=False).passed is False
