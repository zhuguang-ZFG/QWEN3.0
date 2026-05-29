"""Tests for safe execution mode and agent execute endpoint."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_runtime.feature_flags import (
    BLOCKED_COMMANDS,
    EXEC_MODES,
    SHELL_ALLOWLIST,
    ExecutionFeatureFlags,
    is_shell_allowed,
    load_flags,
)
from agent_runtime.real_executor import (
    SAFE_MODE_BLOCKED,
    RealExecutorConfig,
    preflight_real_execution,
)
from agent_runtime.contract import AgentStep, StepKind


# ─── feature_flags tests ─────────────────────────────────────────────


class TestExecMode:
    def test_default_mode_is_dry(self):
        with patch.dict(os.environ, {}, clear=True):
            flags = load_flags()
            assert flags.exec_mode == "dry"
            assert flags.dry_run is True
            assert flags.allow_shell is False

    def test_safe_mode_enables_shell_and_workspace(self):
        with patch.dict(os.environ, {"LIMA_EXEC_MODE": "safe"}, clear=False):
            os.environ["LIMA_EXEC_MODE"] = "safe"
            flags = load_flags()
            assert flags.exec_mode == "safe"
            assert flags.dry_run is False
            assert flags.allow_shell is True
            assert flags.allow_workspace_write is True
            assert flags.allow_network is False

    def test_full_mode_enables_all(self):
        with patch.dict(os.environ, {"LIMA_EXEC_MODE": "full"}, clear=False):
            os.environ["LIMA_EXEC_MODE"] = "full"
            flags = load_flags()
            assert flags.exec_mode == "full"
            assert flags.dry_run is False
            assert flags.allow_shell is True
            assert flags.allow_network is True
            assert flags.allow_workspace_write is True

    def test_invalid_mode_falls_back_to_dry(self):
        with patch.dict(os.environ, {"LIMA_EXEC_MODE": "invalid"}, clear=False):
            os.environ["LIMA_EXEC_MODE"] = "invalid"
            flags = load_flags()
            assert flags.exec_mode == "dry"
            assert flags.dry_run is True

    def test_legacy_env_vars_still_work(self):
        with patch.dict(os.environ, {
            "LIMA_DRY_RUN": "0",
            "LIMA_ALLOW_SHELL": "1",
            "LIMA_EXEC_MODE": "dry",
        }, clear=False):
            flags = load_flags()
            # Legacy overrides should NOT apply when exec_mode is explicitly set
            # exec_mode="dry" means dry_run=True regardless
            assert flags.dry_run is True


class TestShellAllowlist:
    def test_expanded_allowlist_contains_common_tools(self):
        assert "grep" in SHELL_ALLOWLIST
        assert "find" in SHELL_ALLOWLIST
        assert "cat" in SHELL_ALLOWLIST
        assert "head" in SHELL_ALLOWLIST
        assert "tail" in SHELL_ALLOWLIST
        assert "curl" in SHELL_ALLOWLIST
        assert "pytest" in SHELL_ALLOWLIST

    def test_blocked_commands_always_rejected(self):
        for cmd in ("rm", "sudo", "kill", "dd", "shutdown"):
            assert cmd in BLOCKED_COMMANDS

    def test_dry_run_blocks_everything(self):
        flags = ExecutionFeatureFlags(dry_run=True, allow_shell=True, shell_allowlist=SHELL_ALLOWLIST)
        assert is_shell_allowed("echo hello", flags) is False

    def test_safe_shell_allowed_commands(self):
        flags = ExecutionFeatureFlags(
            dry_run=False, allow_shell=True, exec_mode="safe",
            shell_allowlist=SHELL_ALLOWLIST,
        )
        assert is_shell_allowed("echo hello", flags) is True
        assert is_shell_allowed("grep -r foo .", flags) is True
        assert is_shell_allowed("pytest tests/", flags) is True

    def test_blocked_commands_rejected_in_safe_mode(self):
        flags = ExecutionFeatureFlags(
            dry_run=False, allow_shell=True, exec_mode="safe",
            shell_allowlist=SHELL_ALLOWLIST | frozenset({"rm", "sudo"}),
        )
        assert is_shell_allowed("rm -rf /", flags) is False
        assert is_shell_allowed("sudo something", flags) is False

    def test_sudo_prefix_blocked(self):
        flags = ExecutionFeatureFlags(
            dry_run=False, allow_shell=True, exec_mode="full",
            shell_allowlist=SHELL_ALLOWLIST | frozenset({"sudo"}),
        )
        assert is_shell_allowed("sudo rm -rf /", flags) is False


# ─── real_executor preflight tests ────────────────────────────────────


class TestPreflightChecks:
    def _make_step(self, command: str) -> AgentStep:
        return AgentStep(step_id="test", kind=StepKind.SHELL_COMMAND, command=command)

    def test_dry_run_blocks(self):
        config = RealExecutorConfig(enabled=True, dry_run=True, execution_kind="shell")
        step = self._make_step("echo hello")
        result = preflight_real_execution(config, step)
        assert result.passed is False

    def test_disabled_config_blocks(self):
        config = RealExecutorConfig(enabled=False, dry_run=False, execution_kind="shell")
        step = self._make_step("echo hello")
        result = preflight_real_execution(config, step)
        assert result.passed is False

    def test_safe_mode_blocks_dangerous_commands(self):
        config = RealExecutorConfig(
            enabled=True, dry_run=False, execution_kind="shell",
            operator_session_id="test-session",
        )
        flags = ExecutionFeatureFlags(
            dry_run=False, allow_shell=True, exec_mode="safe",
            shell_allowlist=SHELL_ALLOWLIST | frozenset({"rm"}),
        )
        step = self._make_step("rm -rf /")
        result = preflight_real_execution(config, step, flags)
        assert result.passed is False
        assert any("safe_mode_blocked" in f for f in result.checks_failed)

    def test_safe_mode_allows_safe_commands(self):
        config = RealExecutorConfig(
            enabled=True, dry_run=False, execution_kind="shell",
            operator_session_id="test-session",
        )
        flags = ExecutionFeatureFlags(
            dry_run=False, allow_shell=True, exec_mode="safe",
            shell_allowlist=SHELL_ALLOWLIST,
        )
        step = self._make_step("echo hello")
        result = preflight_real_execution(config, step, flags)
        assert result.passed is True

    def test_workspace_blocked_when_not_allowed(self):
        config = RealExecutorConfig(
            enabled=True, dry_run=False, execution_kind="workspace",
            operator_session_id="test-session",
        )
        flags = ExecutionFeatureFlags(
            dry_run=False, allow_workspace_write=False, exec_mode="safe",
        )
        step = self._make_step("/tmp/test.txt")
        result = preflight_real_execution(config, step, flags)
        assert result.passed is False


# ─── agent_execute endpoint tests ─────────────────────────────────────


class TestAgentExecuteEndpoint:
    """Test the /agent/execute endpoint logic (without full HTTP)."""

    def test_detect_execution_kind_shell(self):
        from routes.agent_execute import _detect_execution_kind
        assert _detect_execution_kind("echo hello") == "shell"
        assert _detect_execution_kind("run: ls -la") == "shell"
        assert _detect_execution_kind("grep -r foo .") == "shell"

    def test_detect_execution_kind_git(self):
        from routes.agent_execute import _detect_execution_kind
        assert _detect_execution_kind("git status") == "git"
        assert _detect_execution_kind("git diff") == "git"

    def test_detect_execution_kind_workspace(self):
        from routes.agent_execute import _detect_execution_kind
        assert _detect_execution_kind("write file.py") == "workspace"
        assert _detect_execution_kind("edit config.json") == "workspace"
        assert _detect_execution_kind("create new_module.py") == "workspace"

    def test_command_from_task_strips_prefix(self):
        from routes.agent_execute import _command_from_task
        assert _command_from_task("run: ls -la", "shell") == "ls -la"
        assert _command_from_task("git status", "git") == "git status"
