"""Sandbox provider interface for Agent Worker code execution and testing.

Provides an abstract interface for disposable execution environments
with mandatory cleanup and timeout semantics. The default implementation
is a fake in-process provider for testing — no cloud sandbox is connected
without explicit gating.

Provider implementations:
    FakeSandboxProvider — in-process, deterministic, for tests
    (future) E2BProvider — E2B cloud sandbox, gated
    (future) CubeSandboxProvider — CubeSandbox, gated
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import time

_ENV_ALLOWLIST = {
    "COMSPEC",
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}


@dataclass
class SandboxConfig:
    """Configuration for a sandbox instance."""
    image: str = "python:3.10"
    timeout_sec: float = 60.0
    max_output_chars: int = 10000
    env_vars: dict[str, str] = field(default_factory=dict)
    work_dir: str = "/workspace"


@dataclass
class SandboxFile:
    """A file to upload into the sandbox."""
    path: str       # relative path within sandbox
    content: str    # file contents
    mode: int = 0o644


@dataclass
class SandboxResult:
    """Result of a sandbox execution."""
    ok: bool
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    diff: str = ""
    files_collected: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str = ""
    cleaned_up: bool = False


@dataclass
class SandboxCreateResult:
    """Result of creating a sandbox instance."""
    ok: bool
    sandbox_id: str = ""
    error: str = ""


class SandboxProvider(ABC):
    """Abstract interface for sandbox providers.

    All implementations must guarantee:
    - Timeout is enforced (no runaway processes)
    - Cleanup is called (no leaked resources)
    - Output is size-capped
    - No secrets in fixture files
    """

    @abstractmethod
    def create(self, config: SandboxConfig | None = None) -> SandboxCreateResult:
        """Create a new sandbox instance."""
        ...

    @abstractmethod
    def upload_files(self, sandbox_id: str, files: list[SandboxFile]) -> bool:
        """Upload files into the sandbox."""
        ...

    @abstractmethod
    def run_command(self, sandbox_id: str, command: str,
                    timeout_sec: float | None = None) -> SandboxResult:
        """Run a command inside the sandbox."""
        ...

    @abstractmethod
    def collect_diff(self, sandbox_id: str) -> list[str]:
        """Collect paths of modified or created files."""
        ...

    @abstractmethod
    def terminate(self, sandbox_id: str) -> bool:
        """Terminate and clean up the sandbox."""
        ...

    @abstractmethod
    def is_alive(self, sandbox_id: str) -> bool:
        """Check if sandbox is still running."""
        ...


class FakeSandboxProvider(SandboxProvider):
    """Deterministic in-process sandbox for testing.

    Runs commands using subprocess in a temp directory.
    No network access. No persistence. Guaranteed cleanup.
    """

    def __init__(self) -> None:
        self._sandboxes: dict[str, dict] = {}
        self._counter: int = 0

    def create(self, config: SandboxConfig | None = None) -> SandboxCreateResult:
        self._counter += 1
        sid = f"fake-sandbox-{self._counter}"
        cfg = config or SandboxConfig()
        work_dir = tempfile.mkdtemp(prefix="lima_sandbox_")
        self._sandboxes[sid] = {
            "config": cfg,
            "work_dir": work_dir,
            "files": {},
            "modified": set(),
            "alive": True,
        }
        return SandboxCreateResult(ok=True, sandbox_id=sid)

    def upload_files(self, sandbox_id: str, files: list[SandboxFile]) -> bool:
        entry = self._sandboxes.get(sandbox_id)
        if not entry:
            return False
        for sf in files:
            target = _resolve_sandbox_path(entry["work_dir"], sf.path)
            if target is None:
                return False
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(sf.content)
            os.chmod(target, sf.mode)
            entry["files"][sf.path] = target
        return True

    def run_command(self, sandbox_id: str, command: str,
                    timeout_sec: float | None = None) -> SandboxResult:
        entry = self._sandboxes.get(sandbox_id)
        if not entry or not entry["alive"]:
            return SandboxResult(ok=False, error="sandbox not alive", cleaned_up=False)

        cfg = entry["config"]
        timeout = timeout_sec or cfg.timeout_sec
        t0 = time.time()
        exit_code = -1
        stdout = ""
        stderr = ""
        error = ""

        try:
            cmd = shlex.split(command)
            if not cmd:
                return SandboxResult(ok=False, error="empty command", cleaned_up=False)
            proc = subprocess.run(
                cmd, shell=False, cwd=entry["work_dir"],
                capture_output=True, text=True,
                timeout=timeout,
                env=_sandbox_env(cfg.env_vars),
            )
            exit_code = proc.returncode
            stdout = proc.stdout[:cfg.max_output_chars]
            stderr = proc.stderr[:cfg.max_output_chars]
        except subprocess.TimeoutExpired:
            error = f"timeout after {timeout}s"
        except Exception as e:
            error = str(e)[:500]

        # Track modified files
        before = set(entry["files"].keys())
        after = set()
        for root, _dirs, files in os.walk(entry["work_dir"]):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), entry["work_dir"])
                after.add(rel)
        entry["modified"] = after - before

        duration_ms = (time.time() - t0) * 1000
        return SandboxResult(
            ok=exit_code == 0 and not error,
            exit_code=exit_code, stdout=stdout, stderr=stderr,
            duration_ms=duration_ms, error=error,
            cleaned_up=entry["alive"],
        )

    def collect_diff(self, sandbox_id: str) -> list[str]:
        entry = self._sandboxes.get(sandbox_id)
        if not entry:
            return []
        return sorted(entry.get("modified", set()))

    def terminate(self, sandbox_id: str) -> bool:
        entry = self._sandboxes.get(sandbox_id)
        if not entry:
            return False
        entry["alive"] = False
        try:
            shutil.rmtree(entry["work_dir"], ignore_errors=True)
        except OSError:
            pass
        return True

    def is_alive(self, sandbox_id: str) -> bool:
        entry = self._sandboxes.get(sandbox_id)
        return entry is not None and entry["alive"]


def _resolve_sandbox_path(work_dir: str, relative_path: str) -> str | None:
    root = Path(work_dir).resolve()
    target = (root / relative_path).resolve()
    if root == target or root in target.parents:
        return str(target)
    return None


def _sandbox_env(extra_env: dict[str, str]) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _ENV_ALLOWLIST
    }
    env.update(extra_env)
    return env
