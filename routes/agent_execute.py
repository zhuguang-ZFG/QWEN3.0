"""Agent execution REST endpoint.

POST /agent/execute — run a task through the agent runtime with safe-mode gates.

Execution modes:
  dry  — returns plan only, no real execution
  safe — allowed commands executed with scope restrictions
  full — all allowed commands (dangerous patterns still blocked)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agent", tags=["agent"])
_log = logging.getLogger(__name__)

_admin_token: str = ""


def inject_state(admin_token: str = "") -> None:
    global _admin_token
    _admin_token = admin_token


class ExecuteRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4096, description="Task instruction")
    mode: str = Field(default="auto", description="Execution mode: auto, shell, git, workspace")
    cwd: str = Field(default="", description="Working directory override")
    timeout_sec: float = Field(default=30.0, ge=1.0, le=120.0)
    session_id: str = Field(default="", description="Operator session ID for audit")


class ExecuteResponse(BaseModel):
    ok: bool
    task_id: str
    output: str = ""
    error: str = ""
    exec_mode: str = ""
    blocked_reason: str = ""
    duration_ms: float = 0.0
    evidence: list[str] = Field(default_factory=list)


def _detect_execution_kind(task: str) -> str:
    """Detect the execution kind from the task instruction."""
    stripped = task.strip().lower()
    if stripped.startswith("git ") or stripped.startswith("git\n"):
        return "git"
    if any(stripped.startswith(prefix) for prefix in ("read ", "show ", "list ", "find ", "grep ", "cat ")):
        return "shell"
    if any(stripped.startswith(prefix) for prefix in ("write ", "edit ", "create ", "patch ", "save ")):
        return "workspace"
    return "shell"


def _command_from_task(task: str, kind: str) -> str:
    """Extract the actual command from the task instruction."""
    stripped = task.strip()
    if kind == "shell":
        # Strip common prefixes
        for prefix in ("run: ", "execute: ", "shell: ", ""):
            if stripped.lower().startswith(prefix):
                return stripped[len(prefix):].strip()
        return stripped
    if kind == "git":
        return stripped
    if kind == "workspace":
        return stripped
    return stripped


@router.post("/execute", response_model=ExecuteResponse)
async def execute_task(req: ExecuteRequest) -> ExecuteResponse:
    """Execute a task through the agent runtime."""
    from agent_runtime.feature_flags import load_flags
    from agent_runtime.real_executor import (
        RealExecutorConfig,
        preflight_real_execution,
    )
    from agent_runtime.contract import AgentStep, StepKind

    t0 = time.time()
    task_id = f"exec-{uuid.uuid4().hex[:12]}"

    flags = load_flags()

    # Dry mode: plan only, no execution
    if flags.dry_run and flags.exec_mode == "dry":
        _log.info("execute_task dry_run task_id=%s task=%s", task_id, req.task[:80])
        return ExecuteResponse(
            ok=True,
            task_id=task_id,
            output="[DRY RUN] Task received but execution is disabled. "
            "Set LIMA_EXEC_MODE=safe or LIMA_EXEC_MODE=full to enable.",
            exec_mode="dry",
            duration_ms=(time.time() - t0) * 1000,
        )

    # Detect execution kind
    kind = req.mode if req.mode in ("shell", "git", "workspace") else _detect_execution_kind(req.task)
    command = _command_from_task(req.task, kind)

    # Build preflight config
    config = RealExecutorConfig(
        enabled=True,
        dry_run=False,
        execution_kind=kind,
        operator_session_id=req.session_id or f"api-{task_id}",
        required_audit_refs=[task_id],
    )

    step = AgentStep(
        step_id=task_id,
        kind=StepKind.SHELL_COMMAND if kind in ("shell", "git") else StepKind.NOOP,
        command=command,
        timeout_sec=req.timeout_sec,
    )

    # Run preflight checks
    preflight = preflight_real_execution(config, step, flags)

    if not preflight.passed:
        _log.warning("execute_task blocked task_id=%s reason=%s", task_id, preflight.blocked_reason)
        return ExecuteResponse(
            ok=False,
            task_id=task_id,
            error=f"Blocked: {preflight.blocked_reason}",
            exec_mode=flags.exec_mode,
            blocked_reason=preflight.blocked_reason,
            duration_ms=(time.time() - t0) * 1000,
            evidence=preflight.checks_failed[:5],
        )

    # Execute via the appropriate executor
    if kind == "shell":
        from agent_runtime.shell_executor import shell_execute
        result = shell_execute(
            command,
            flags=flags,
            cwd=req.cwd or None,
            timeout_sec=req.timeout_sec,
        )
    elif kind == "git":
        from agent_runtime.git_executor import git_execute
        result = git_execute(
            command,
            flags=flags,
            timeout_sec=req.timeout_sec,
        )
    else:
        return ExecuteResponse(
            ok=False,
            task_id=task_id,
            error=f"Execution kind '{kind}' not yet supported via API",
            exec_mode=flags.exec_mode,
            duration_ms=(time.time() - t0) * 1000,
        )

    _log.info(
        "execute_task done task_id=%s ok=%s duration=%.0fms",
        task_id,
        result.ok,
        result.duration_ms,
    )

    return ExecuteResponse(
        ok=result.ok,
        task_id=task_id,
        output=result.output[:8192] if result.output else "",
        error=result.error[:2048] if result.error else "",
        exec_mode=flags.exec_mode,
        duration_ms=result.duration_ms,
        evidence=result.evidence[:10],
    )


@router.get("/execute/status")
async def execute_status() -> dict:
    """Check execution capability status."""
    from agent_runtime.feature_flags import load_flags
    flags = load_flags()
    return {
        "exec_mode": flags.exec_mode,
        "dry_run": flags.dry_run,
        "allow_shell": flags.allow_shell,
        "allow_network": flags.allow_network,
        "allow_workspace_write": flags.allow_workspace_write,
        "shell_allowlist_count": len(flags.shell_allowlist),
    }
