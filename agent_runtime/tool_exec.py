"""Tool execution boundary for fake/no-op executors with safe fallback.

Never executes real shell, network, or workspace writes by default.
Each executor returns a structured result with evidence.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from agent_runtime.contract import redact


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""
    evidence: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    executed: bool = False  # True if real execution happened (only with gate)


class ToolExecutor(ABC):
    @abstractmethod
    def run(self, command: str, timeout_sec: float = 30.0) -> ToolResult:
        ...


class NoopToolExecutor(ToolExecutor):
    """Always returns dry-run result. Never executes anything."""

    def run(self, command: str, timeout_sec: float = 30.0) -> ToolResult:
        safe_command = redact(command[:200])
        return ToolResult(
            ok=True,
            output=f"[noop] Would execute: {safe_command}",
            evidence=["noop_dry_run"],
            executed=False,
        )


class FakeToolExecutor(ToolExecutor):
    """Returns deterministic fake output for predefined commands."""

    _DEFAULT_RESPONSES: dict[str, str] = {
        "pytest": "[fake] 3 passed, 0 failed",
        "echo": "[fake] echo output",
        "ls": "[fake] file1.py  file2.py",
        "git status": "[fake] On branch main, nothing to commit",
    }

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = dict(self._DEFAULT_RESPONSES)
        if responses:
            self._responses.update(responses)

    def run(self, command: str, timeout_sec: float = 30.0) -> ToolResult:
        t0 = time.time()
        for prefix, response in self._responses.items():
            if command.strip().startswith(prefix):
                return ToolResult(
                    ok=True, output=response,
                    evidence=[f"fake_{prefix.split()[0]}"],
                    duration_ms=(time.time() - t0) * 1000,
                    executed=False,
                )
        return ToolResult(
            ok=True,
            output=f"[fake] Unknown command: {redact(command[:200])}",
            evidence=["fake_unknown"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )


class ShellBlockedExecutor(ToolExecutor):
    """Always blocks shell execution, recording the blocked attempt."""

    def run(self, command: str, timeout_sec: float = 30.0) -> ToolResult:
        return ToolResult(
            ok=False,
            error="shell execution blocked by runtime policy",
            evidence=["shell_blocked"],
            executed=False,
        )


def get_executor(
    allow_shell: bool = False,
    fake_outputs: dict[str, str] | None = None,
) -> ToolExecutor:
    if allow_shell:
        return ShellBlockedExecutor()  # still blocked, just records differently
    if fake_outputs:
        return FakeToolExecutor(fake_outputs)
    return NoopToolExecutor()
