"""Invoke MiMo CLI with Agent-oriented flags (trust, dir, files, optional agent/model)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InvokeResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    command: list[str]


def mimo_binary() -> str | None:
    return shutil.which("mimo")


def build_command(
    prompt: str,
    workspace: Path,
    *,
    attach_files: list[Path] | None = None,
    agent: str | None = None,
    model: str | None = None,
    session_continue: bool = False,
) -> list[str]:
    binary = mimo_binary()
    if not binary:
        raise FileNotFoundError("mimo CLI not found on PATH")

    cmd: list[str] = [binary, "run", prompt, "--dir", str(workspace), "--trust"]
    if agent:
        cmd.extend(["--agent", agent])
    model = model or os.environ.get("MIMO_MCP_MODEL", "").strip()
    if model:
        cmd.extend(["-m", model])
    if session_continue:
        cmd.append("--continue")
    for path in attach_files or []:
        if path.is_file():
            cmd.extend(["-f", str(path)])
    if os.environ.get("MIMO_MCP_SKIP_PERMISSIONS", "").strip() in {"1", "true", "yes"}:
        cmd.append("--dangerously-skip-permissions")
    return cmd


def run_mimo(
    prompt: str,
    workspace: Path,
    *,
    attach_files: list[Path] | None = None,
    agent: str | None = None,
    model: str | None = None,
    session_continue: bool = False,
    timeout: int = 180,
    output_path: Path | None = None,
) -> InvokeResult:
    cmd = build_command(
        prompt,
        workspace,
        attach_files=attach_files,
        agent=agent,
        model=model,
        session_continue=session_continue,
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        body = f"ERROR: timeout after {timeout}s\n"
        if output_path:
            output_path.write_text(body, encoding="utf-8")
        return InvokeResult(False, 124, "", body, cmd)

    body = proc.stdout or ""
    if proc.stderr:
        body = f"{body}\n\n--- stderr ---\n{proc.stderr}".strip()
    if proc.returncode != 0:
        body = f"ERROR: exit {proc.returncode}\n{body}".strip()
    if output_path:
        output_path.write_text(body + "\n", encoding="utf-8")

    ok = proc.returncode == 0 and not body.startswith("ERROR:")
    return InvokeResult(ok, proc.returncode, proc.stdout or "", proc.stderr or "", cmd)
