from __future__ import annotations

import sys
from pathlib import Path

import pytest

from safe_command import UnsafeCommandError, parse_safe_command, run_safe_command


def test_parse_safe_command_accepts_allowlisted_command() -> None:
    assert parse_safe_command("pytest --tb=short -q", {"pytest"}) == ["pytest", "--tb=short", "-q"]


def test_parse_safe_command_rejects_shell_metacharacters() -> None:
    with pytest.raises(UnsafeCommandError):
        parse_safe_command("pytest -q; whoami", {"pytest"})
    with pytest.raises(UnsafeCommandError):
        parse_safe_command("pytest -q | tail -5", {"pytest"})


def test_parse_safe_command_rejects_unlisted_executable() -> None:
    with pytest.raises(UnsafeCommandError):
        parse_safe_command("curl https://example.com", {"pytest"})


def test_run_safe_command_uses_argument_list() -> None:
    result = run_safe_command(
        f'"{sys.executable}" -c "print(123)"',
        allowed_commands={Path(sys.executable).name},
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "123"
