"""Tests for M29-M33: sessions, flags, sandbox, network, and hardening."""

from agent_runtime.approval import ApprovalGate
from agent_runtime.approval_session import (
    ApprovalSession,
    approve_session,
    deny_session,
    format_session,
    open_session,
)
from agent_runtime.audit_trail import AuditTrail
from agent_runtime.contract import AgentStep, StepKind
from agent_runtime.feature_flags import (
    ExecutionFeatureFlags,
    is_network_allowed,
    is_shell_allowed,
    is_workspace_write_allowed,
    load_flags,
    preflight_audit_check,
)
from agent_runtime.network_policy import NetworkDecision, NetworkPolicy, build_default_policy
from agent_runtime.workspace_sandbox import PatchRecord, WorkspaceSandbox, WriteResult


def test_open_session():
    gate = ApprovalGate(dry_run=False)
    step = AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test")
    req = gate.request_approval(step)
    session = open_session(req)
    assert session.approval_id == req.approval_id
    assert session.kind == "shell_command"


def test_approve_session(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=False)
    req = gate.request_approval(AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test"))
    session = open_session(req)
    approve_session(gate, session, operator="alice")
    assert session.status == "approved"
    assert session.decided_at > 0
    assert session.decided_by == "alice"
    assert session.audit_refs


def test_deny_session(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    gate = ApprovalGate(dry_run=False)
    req = gate.request_approval(AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="test"))
    session = open_session(req)
    deny_session(gate, session, reason="not safe")
    assert session.status == "denied"
    assert any("not safe" in evidence for evidence in session.evidence)


def test_format_session():
    gate = ApprovalGate(dry_run=False)
    req = gate.request_approval(
        AgentStep(step_id="s1", kind=StepKind.SHELL_COMMAND, goal="deploy", command="echo hi")
    )
    session = open_session(req, evidence=["review by operator"])
    text = format_session(session)
    assert session.approval_id in text
    assert "deploy" in text
    assert "echo hi" in text


def test_session_to_dict_redacts_secrets():
    session = ApprovalSession(
        approval_id="a1",
        kind="shell_command",
        command="api_key=supersecretvalue1234567890",
        evidence=["token=supersecretvalue1234567890"],
    )
    data = session.to_dict()
    assert data["command"] == "[REDACTED]"
    assert data["evidence"] == ["[REDACTED]"]


def test_load_flags_defaults(monkeypatch):
    monkeypatch.delenv("LIMA_ALLOW_SHELL", raising=False)
    monkeypatch.delenv("LIMA_DRY_RUN", raising=False)
    flags = load_flags()
    assert flags.dry_run is True
    assert flags.allow_shell is False
    assert flags.any_real_execution is False


def test_is_shell_allowed_default_off():
    flags = ExecutionFeatureFlags()
    assert is_shell_allowed("echo hello", flags) is False


def test_is_shell_allowed_requires_flag_allowlist_and_non_dry_run():
    flags = ExecutionFeatureFlags(
        allow_shell=True,
        dry_run=False,
        shell_allowlist=frozenset({"pytest"}),
    )
    assert is_shell_allowed("pytest --tb=short", flags) is True
    assert is_shell_allowed("rm -rf /", flags) is False
    dry = ExecutionFeatureFlags(allow_shell=True, shell_allowlist=frozenset({"pytest"}))
    assert is_shell_allowed("pytest", dry) is False


def test_load_flags_parses_env_allowlists(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_ALLOW_SHELL", "1")
    monkeypatch.setenv("LIMA_DRY_RUN", "0")
    monkeypatch.setenv("LIMA_SHELL_ALLOWLIST", "pytest,git")
    monkeypatch.setenv("LIMA_ALLOW_WORKSPACE_WRITE", "1")
    monkeypatch.setenv("LIMA_WORKSPACE_ALLOWLIST", str(tmp_path))
    flags = load_flags()
    assert is_shell_allowed("git status", flags) is True
    assert is_workspace_write_allowed(str(tmp_path / "ok.txt"), flags) is True


def test_is_network_allowed_default_off():
    flags = ExecutionFeatureFlags(
        allow_network=True,
        dry_run=False,
        network_domain_allowlist=frozenset(),
    )
    assert is_network_allowed("https://api.example.com", flags) is False


def test_is_network_allowed_exact_or_subdomain_only():
    flags = ExecutionFeatureFlags(
        allow_network=True,
        dry_run=False,
        network_domain_allowlist=frozenset({"example.com"}),
    )
    assert is_network_allowed("https://api.example.com", flags) is True
    assert is_network_allowed("https://badexample.com", flags) is False


def test_is_workspace_write_allowed_default_off(tmp_path):
    flags = ExecutionFeatureFlags(
        allow_workspace_write=True,
        dry_run=False,
        workspace_allowlist=frozenset(),
    )
    assert is_workspace_write_allowed(str(tmp_path / "file.py"), flags) is False


def test_preflight_audit_check(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    result = preflight_audit_check(task_id="t1", worker_id="w1")
    assert result["dry_run"] is True
    assert result["allowed"] is False
    assert result["task_id"] == "t1"


def test_sandbox_dry_run_default():
    sandbox = WorkspaceSandbox(dry_run=True)
    result = sandbox.apply_patches([
        PatchRecord(file_path="test.py", original="x=1", patched="x=2"),
    ])
    assert result.ok is True
    assert result.dry_run is True
    assert result.files_changed == 1
    assert result.patches[0].applied is False


def test_sandbox_preview():
    sandbox = WorkspaceSandbox(dry_run=True)
    patches = [PatchRecord(file_path="a.py", original="x=1\ny=2", patched="x=1\ny=3")]
    previews = sandbox.preview(patches)
    assert any("+ y=3" in preview for preview in previews)


def test_sandbox_rejects_path_escape_even_in_dry_run(tmp_path):
    sandbox = WorkspaceSandbox(root=str(tmp_path), dry_run=True)
    result = sandbox.apply_patches([
        PatchRecord(file_path="../escape.txt", original="", patched="x"),
    ])
    assert result.ok is False
    assert "escapes" in result.error


def test_sandbox_rollback_not_applied():
    sandbox = WorkspaceSandbox(dry_run=True)
    result = sandbox.apply_patches([PatchRecord(file_path="f.py", original="a", patched="b")])
    assert sandbox.rollback(result.patches[0]) is False


def test_sandbox_non_dry_run_writes(tmp_path):
    sandbox = WorkspaceSandbox(root=str(tmp_path), dry_run=False)
    target = tmp_path / "test.txt"
    target.write_text("original", encoding="utf-8")
    result = sandbox.apply_patches([
        PatchRecord(file_path="test.txt", original="original", patched="modified"),
    ])
    assert result.ok is True
    assert result.dry_run is False
    assert target.read_text(encoding="utf-8") == "modified"


def test_sandbox_non_dry_rollback(tmp_path):
    sandbox = WorkspaceSandbox(root=str(tmp_path), dry_run=False)
    target = tmp_path / "test.txt"
    target.write_text("original", encoding="utf-8")
    result = sandbox.apply_patches([
        PatchRecord(file_path="test.txt", original="original", patched="modified"),
    ])
    assert sandbox.rollback(result.patches[0]) is True
    assert target.read_text(encoding="utf-8") == "original"


def test_network_policy_empty_allowlist_blocks_all():
    policy = NetworkPolicy()
    decision = policy.check_request("https://api.example.com/data")
    assert decision.allowed is False
    assert "no domains allowlisted" in decision.reason


def test_network_policy_allowlisted_exact_and_subdomain():
    policy = NetworkPolicy(domain_allowlist=frozenset({"example.com"}))
    assert policy.check_request("https://example.com/data").allowed is True
    assert policy.check_request("https://api.example.com/data").allowed is True


def test_network_policy_does_not_match_suffix_confusion():
    policy = NetworkPolicy(domain_allowlist=frozenset({"example.com"}))
    decision = policy.check_request("https://badexample.com")
    assert decision.allowed is False


def test_network_policy_invalid_url():
    policy = NetworkPolicy(domain_allowlist=frozenset({"example.com"}))
    decision = policy.check_request("not-a-url")
    assert decision.allowed is False


def test_network_policy_rate_limit():
    policy = NetworkPolicy(
        domain_allowlist=frozenset({"api.test"}),
        max_requests_per_minute=2,
    )
    assert policy.check_request("https://api.test/1").allowed is True
    assert policy.check_request("https://api.test/2").allowed is True
    assert policy.check_request("https://api.test/3").allowed is False


def test_build_default_policy_blocks_all():
    policy = build_default_policy()
    assert policy.check_request("https://anything.com").allowed is False


def test_full_gated_pipeline_no_real_execution():
    flags = load_flags()
    assert flags.dry_run is True
    assert is_shell_allowed("pytest", flags) is False

    sandbox = WorkspaceSandbox(dry_run=True)
    result = sandbox.apply_patches([PatchRecord(file_path="x.py", original="a", patched="b")])
    assert result.dry_run is True

    policy = build_default_policy()
    assert policy.check_request("https://x.com").allowed is False


def test_audit_integration_across_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_AUDIT_TRAIL", str(tmp_path / "audit.jsonl"))
    preflight_audit_check(task_id="t1")

    sandbox = WorkspaceSandbox(dry_run=True)
    sandbox.apply_patches([PatchRecord(file_path="x.py", original="a", patched="b")])

    trail = AuditTrail(str(tmp_path / "audit.jsonl"))
    records = trail.query()
    assert len(records) >= 2


def test_public_dataclasses_construct():
    assert WriteResult(ok=True).ok is True
    assert NetworkDecision(allowed=False).allowed is False
