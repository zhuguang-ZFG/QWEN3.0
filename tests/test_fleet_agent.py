"""Tests for fleet.agent."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

MOCK_NOW = 2_000_000_000.0


class TestFleetAgent:
    def test_detect_capabilities(self):
        from fleet.agent import detect_capabilities

        caps = detect_capabilities()
        assert "gpu" in caps
        assert "cpu_cores" in caps
        assert "shell" in caps
        assert isinstance(caps["models"], list)

    def test_run_shell_task_rejects_shell_metacharacters(self):
        from fleet.agent import run_shell_task

        result, error = run_shell_task("pytest -q; whoami")

        assert result == ""
        assert "unsafe command rejected" in error

    def test_run_shell_task_uses_safe_subprocess_boundary(self):
        from fleet.agent import run_shell_task

        with patch("fleet.agent.run_safe_command") as run:
            run.return_value.stdout = "ok\n"
            run.return_value.stderr = ""
            run.return_value.returncode = 0

            result, error = run_shell_task("pytest -q")

        assert result == "ok\n"
        assert error == ""
        assert run.call_args.kwargs["allowed_commands"]


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
