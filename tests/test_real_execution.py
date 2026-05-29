"""Tests for real agent execution: shell, git, network executors + preflight gates."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_runtime.feature_flags import (
    ExecutionFeatureFlags,
    is_network_allowed,
    is_shell_allowed,
)
from agent_runtime.git_executor import _extract_git_subcommand, git_execute
from agent_runtime.network_executor import network_execute
from agent_runtime.real_executor import (
    PreflightResult,
    RealExecutorConfig,
    RealToolExecutor,
    preflight_real_execution,
)
from agent_runtime.contract import AgentStep, StepKind
from agent_runtime.shell_executor import shell_execute
from agent_runtime.tool_exec import ToolResult


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    def test_shell_allowed_when_enabled(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"echo", "git"}),
        )
        assert is_shell_allowed("echo hello", flags) is True

    def test_shell_blocked_when_dry_run(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=True,
            shell_allowlist=frozenset({"echo"}),
        )
        assert is_shell_allowed("echo hello", flags) is False

    def test_shell_blocked_when_command_not_in_allowlist(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"echo"}),
        )
        assert is_shell_allowed("rm -rf /", flags) is False

    def test_network_allowed_when_domain_in_allowlist(self):
        flags = ExecutionFeatureFlags(
            allow_network=True, dry_run=False,
            network_domain_allowlist=frozenset({"example.com"}),
        )
        assert is_network_allowed("https://example.com/api", flags) is True

    def test_network_blocked_when_domain_not_in_allowlist(self):
        flags = ExecutionFeatureFlags(
            allow_network=True, dry_run=False,
            network_domain_allowlist=frozenset({"example.com"}),
        )
        assert is_network_allowed("https://evil.com/api", flags) is False

    def test_network_blocked_when_no_allowlist(self):
        flags = ExecutionFeatureFlags(
            allow_network=True, dry_run=False,
            network_domain_allowlist=frozenset(),
        )
        assert is_network_allowed("https://example.com/api", flags) is False


# ---------------------------------------------------------------------------
# Shell executor
# ---------------------------------------------------------------------------

class TestShellExecutor:
    def test_echo_success(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"echo"}),
        )
        result = shell_execute("echo hello world", flags=flags)
        assert result.ok is True
        assert result.executed is True
        assert "hello world" in result.output
        assert any("shell_exit:0" in e for e in result.evidence)

    def test_failing_command(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"python"}),
        )
        result = shell_execute("python -c 'import sys; sys.exit(1)'", flags=flags)
        assert result.ok is False
        assert result.executed is True
        assert "exit 1" in result.output

    def test_timeout_kills_process(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"python"}),
        )
        result = shell_execute(
            "python -c 'import time; time.sleep(60)'",
            flags=flags,
            timeout_sec=0.5,
        )
        assert result.ok is False
        assert result.executed is True
        assert any("timeout" in e for e in result.evidence)

    def test_gate_blocked_when_dry_run(self):
        flags = ExecutionFeatureFlags(dry_run=True, allow_shell=True)
        result = shell_execute("echo hi", flags=flags)
        assert result.ok is False
        assert result.executed is False
        assert any("blocked" in e for e in result.evidence)

    def test_gate_blocked_when_command_not_in_allowlist(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"echo"}),
        )
        result = shell_execute("rm -rf /tmp/test", flags=flags)
        assert result.ok is False
        assert result.executed is False

    def test_output_truncation(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"python"}),
        )
        cmd = "python -c \"print('x' * 100000)\""
        result = shell_execute(cmd, flags=flags)
        assert result.ok is True
        assert len(result.output) <= 64 * 1024


# ---------------------------------------------------------------------------
# Git executor
# ---------------------------------------------------------------------------

class TestGitExecutor:
    def test_extract_subcommand(self):
        assert _extract_git_subcommand("git status") == "status"
        assert _extract_git_subcommand("git diff --stat") == "diff"
        assert _extract_git_subcommand("git push origin main") == "push"
        assert _extract_git_subcommand("not git") == ""
        assert _extract_git_subcommand("git") == ""

    def test_allowed_subcommand(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"git"}),
        )
        result = git_execute("git status", flags=flags)
        assert result.executed is True
        assert any("git_status" in e for e in result.evidence)

    def test_blocked_push(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"git"}),
        )
        result = git_execute("git push origin main", flags=flags)
        assert result.ok is False
        assert result.executed is False
        assert any("blocked" in e for e in result.evidence)

    def test_blocked_pull(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"git"}),
        )
        result = git_execute("git pull", flags=flags)
        assert result.ok is False
        assert result.executed is False

    def test_git_diff_in_temp_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True,
            )
            Path(tmpdir, "test.txt").write_text("hello")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True,
            )

            flags = ExecutionFeatureFlags(
                allow_shell=True, dry_run=False,
                shell_allowlist=frozenset({"git"}),
            )
            result = git_execute("git log --oneline -1", flags=flags, cwd=tmpdir)
            assert result.ok is True
            assert "init" in result.output

    def test_unknown_subcommand(self):
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"git"}),
        )
        result = git_execute("git cherry-pick abc", flags=flags)
        assert result.ok is False
        assert "not in allowlist" in result.error


# ---------------------------------------------------------------------------
# Network executor
# ---------------------------------------------------------------------------

class TestNetworkExecutor:
    def test_gate_blocked(self):
        flags = ExecutionFeatureFlags(dry_run=True, allow_network=True)
        result = network_execute("https://httpbin.org/get", flags=flags)
        assert result.ok is False
        assert result.executed is False

    def test_domain_not_in_allowlist(self):
        flags = ExecutionFeatureFlags(
            allow_network=True, dry_run=False,
            network_domain_allowlist=frozenset({"example.com"}),
        )
        result = network_execute("https://httpbin.org/get", flags=flags)
        assert result.ok is False
        assert result.executed is False


# ---------------------------------------------------------------------------
# Preflight gates
# ---------------------------------------------------------------------------

class TestPreflight:
    def _make_config(self, **kwargs) -> RealExecutorConfig:
        defaults = dict(
            enabled=True,
            dry_run=False,
            execution_kind="shell",
            operator_session_id="test-session",
            required_audit_refs=["ref1"],
        )
        defaults.update(kwargs)
        return RealExecutorConfig(**defaults)

    def _make_step(self, command: str = "echo test") -> AgentStep:
        return AgentStep(
            step_id="test-step",
            kind=StepKind.SHELL_COMMAND,
            command=command,
        )

    def _open_flags(self) -> ExecutionFeatureFlags:
        return ExecutionFeatureFlags(
            allow_shell=True,
            allow_network=False,
            allow_workspace_write=False,
            dry_run=False,
            shell_allowlist=frozenset({"echo", "git", "pytest", "python"}),
        )

    def test_preflight_passes_when_all_gates_open(self):
        config = self._make_config()
        step = self._make_step()
        result = preflight_real_execution(config, step, self._open_flags())
        assert result.passed is True
        assert len(result.checks_failed) == 0

    def test_preflight_blocks_when_dry_run(self):
        config = self._make_config(dry_run=True)
        step = self._make_step()
        result = preflight_real_execution(config, step, self._open_flags())
        assert result.passed is False
        assert any("dry_run" in c for c in result.checks_failed)

    def test_preflight_blocks_when_disabled(self):
        config = self._make_config(enabled=False)
        step = self._make_step()
        result = preflight_real_execution(config, step, self._open_flags())
        assert result.passed is False

    def test_preflight_blocks_when_no_operator_session(self):
        config = self._make_config(operator_session_id="")
        step = self._make_step()
        result = preflight_real_execution(config, step, self._open_flags())
        assert result.passed is False

    def test_preflight_allows_empty_audit_refs(self):
        """audit_refs no longer required ( safe mode change )."""
        config = self._make_config(required_audit_refs=[])
        step = self._make_step()
        result = preflight_real_execution(config, step, self._open_flags())
        assert result.passed is True

    def test_preflight_blocks_unknown_execution_kind(self):
        config = self._make_config(execution_kind="unknown")
        step = self._make_step()
        result = preflight_real_execution(config, step, self._open_flags())
        assert result.passed is False

    def test_preflight_git_requires_shell_allowlist(self):
        config = self._make_config(execution_kind="git")
        step = self._make_step("git status")
        flags = ExecutionFeatureFlags(
            allow_shell=True, dry_run=False,
            shell_allowlist=frozenset({"echo"}),  # git NOT in list
        )
        result = preflight_real_execution(config, step, flags)
        assert result.passed is False


# ---------------------------------------------------------------------------
# RealToolExecutor
# ---------------------------------------------------------------------------

class TestRealToolExecutor:
    def test_returns_blocked_when_gates_not_met(self):
        executor = RealToolExecutor(
            config=RealExecutorConfig(enabled=False),
            flags=ExecutionFeatureFlags(dry_run=True),
        )
        result = executor.run("echo test")
        assert result.ok is False
        assert result.executed is False
        assert executor.last_preflight is not None
        assert executor.last_preflight.passed is False

    def test_dispatches_shell_when_gates_open(self):
        executor = RealToolExecutor(
            config=RealExecutorConfig(
                enabled=True,
                dry_run=False,
                execution_kind="shell",
                operator_session_id="test",
                required_audit_refs=["ref1"],
            ),
            flags=ExecutionFeatureFlags(
                allow_shell=True,
                dry_run=False,
                shell_allowlist=frozenset({"echo"}),
            ),
        )
        result = executor.run("echo hello from executor")
        assert result.ok is True
        assert result.executed is True
        assert "hello from executor" in result.output

    def test_dispatches_git_when_kind_git(self):
        executor = RealToolExecutor(
            config=RealExecutorConfig(
                enabled=True,
                dry_run=False,
                execution_kind="git",
                operator_session_id="test",
                required_audit_refs=["ref1"],
            ),
            flags=ExecutionFeatureFlags(
                allow_shell=True,
                dry_run=False,
                shell_allowlist=frozenset({"git"}),
            ),
        )
        result = executor.run("git status")
        assert result.executed is True
        assert any("git_status" in e for e in result.evidence)

    def test_blocks_git_push(self):
        executor = RealToolExecutor(
            config=RealExecutorConfig(
                enabled=True,
                dry_run=False,
                execution_kind="git",
                operator_session_id="test",
                required_audit_refs=["ref1"],
            ),
            flags=ExecutionFeatureFlags(
                allow_shell=True,
                dry_run=False,
                shell_allowlist=frozenset({"git"}),
            ),
        )
        result = executor.run("git push origin main")
        assert result.ok is False
        assert result.executed is False

    def test_unsupported_kind(self):
        executor = RealToolExecutor(
            config=RealExecutorConfig(
                enabled=True,
                dry_run=False,
                execution_kind="shell",
                operator_session_id="test",
                required_audit_refs=["ref1"],
            ),
            flags=ExecutionFeatureFlags(
                allow_shell=True,
                dry_run=False,
                shell_allowlist=frozenset({"echo"}),
            ),
        )
        executor.config.execution_kind = "bogus"
        result = executor.run("echo test")
        assert result.ok is False
        assert "unknown execution kind" in result.error
