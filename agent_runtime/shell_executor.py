"""Shell command executor with timeout, output capture, and signal handling.

Runs subprocess commands in a bounded sandbox. Never uses shell=True.
All execution gated behind LIMA_DRY_RUN=0 + LIMA_ALLOW_SHELL=1.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time

from agent_runtime.contract import redact
from agent_runtime.feature_flags import ExecutionFeatureFlags, is_shell_allowed
from agent_runtime.tool_exec import ToolResult

_log = logging.getLogger(__name__)

_MAX_OUTPUT_BYTES = 64 * 1024
_DEFAULT_TIMEOUT_SEC = 30.0


def shell_execute(
    command: str,
    *,
    flags: ExecutionFeatureFlags,
    cwd: str | None = None,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    env_extra: dict[str, str] | None = None,
) -> ToolResult:
    t0 = time.time()

    if not is_shell_allowed(command, flags):
        return ToolResult(
            ok=False,
            error="shell not allowed or command not in allowlist",
            evidence=["shell_gate_blocked"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    args = _parse_command_args(command)
    if not args:
        return ToolResult(
            ok=False,
            error="empty command",
            evidence=["shell_empty_command"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    run_env = {**os.environ}
    if env_extra:
        run_env.update(env_extra)

    effective_cwd = cwd or os.getcwd()
    timeout = min(timeout_sec, _DEFAULT_TIMEOUT_SEC)

    _log.info("shell_execute: %s (cwd=%s, timeout=%s)", redact(command[:100]), effective_cwd, timeout)

    if args[0].lower() == "echo":
        output = " ".join(args[1:])
        return ToolResult(
            ok=True,
            output=f"{output}\n" if output else "\n",
            error="",
            evidence=["shell_exit:0", "shell_builtin:echo"],
            duration_ms=(time.time() - t0) * 1000,
            executed=True,
        )

    try:
        proc = subprocess.run(
            args,
            cwd=effective_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=run_env,
        )
        stdout = proc.stdout[:_MAX_OUTPUT_BYTES] if proc.stdout else ""
        stderr = proc.stderr[:_MAX_OUTPUT_BYTES] if proc.stderr else ""
        duration = (time.time() - t0) * 1000
        ok = proc.returncode == 0
        output = stdout if ok else f"exit {proc.returncode}\n{stderr}"
        output = output[:_MAX_OUTPUT_BYTES]

        return ToolResult(
            ok=ok,
            output=output,
            error=stderr[:_MAX_OUTPUT_BYTES] if not ok else "",
            evidence=[
                f"shell_exit:{proc.returncode}",
                f"shell_duration:{duration:.0f}ms",
            ],
            duration_ms=duration,
            executed=True,
        )

    except subprocess.TimeoutExpired as exc:
        _kill_proc_tree(getattr(exc, "proc", None))
        stdout_raw = exc.stdout or b""
        stdout = stdout_raw[:_MAX_OUTPUT_BYTES] if isinstance(stdout_raw, bytes) else str(stdout_raw)[:_MAX_OUTPUT_BYTES]
        duration = (time.time() - t0) * 1000
        return ToolResult(
            ok=False,
            output=stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout,
            error=f"timeout after {timeout}s",
            evidence=["shell_timeout", f"shell_duration:{duration:.0f}ms"],
            duration_ms=duration,
            executed=True,
        )

    except FileNotFoundError:
        return ToolResult(
            ok=False,
            error=f"command not found: {args[0]}",
            evidence=["shell_file_not_found"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    except OSError as exc:
        return ToolResult(
            ok=False,
            error=f"os error: {exc}",
            evidence=["shell_os_error"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )


def _parse_command_args(command: str) -> list[str]:
    import shlex

    try:
        return shlex.split(command)
    except ValueError:
        return command.strip().split() if command.strip() else []


def _kill_proc_tree(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if os.name == "nt":
            proc.kill()
        else:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                proc.kill()
            time.sleep(0.1)
            if proc.poll() is None:
                proc.kill()
    except (ProcessLookupError, OSError):
        pass
