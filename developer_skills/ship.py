"""Ship workflow: git status → diff → stage → commit → push.

Automates the delivery pipeline for LiMa milestones.
"""

from __future__ import annotations

import logging
import subprocess
import time

from developer_skills import SkillResult

_log = logging.getLogger(__name__)


def ship(
    message: str = "",
    *,
    stage_all: bool = False,
    push: bool = True,
    remote: str = "origin",
) -> SkillResult:
    """Execute git ship: stage → commit → push.

    Args:
        message: Commit message. If empty, generates from diff summary.
        stage_all: If True, stage all changed files. Otherwise only explicitly changed.
        push: Whether to push after commit.
        remote: Remote to push to.
    """
    t0 = time.time()
    details: list[str] = []
    evidence: list[str] = []

    status = _run_git(["status", "--short"]).stdout
    if not status.strip():
        return SkillResult(
            ok=True, skill="ship",
            summary="Nothing to ship — working tree clean",
            evidence=["ship_clean"],
        )

    details.append("## Changes:")
    for line in status.strip().split("\n")[:10]:
        details.append(f"  {line}")

    if stage_all:
        _run_git(["add", "-A"])
        evidence.append("staged_all")
    else:
        evidence.append("staged_selective")

    diff_stat = _run_git(["diff", "--cached", "--stat"]).stdout
    details.append(f"## Staged:\n  {diff_stat.strip()}")

    if not message:
        message = _generate_message(status)
    evidence.append(f"commit_message:{message[:60]}")

    commit_result = _run_git(["commit", "-m", message])
    if commit_result.returncode != 0:
        return SkillResult(
            ok=False, skill="ship",
            summary=f"Commit failed: {commit_result.stderr[:200]}",
            details=details,
            evidence=evidence + ["ship_commit_failed"],
        )

    commit_hash = _run_git(["rev-parse", "--short", "HEAD"]).stdout.strip()
    details.append(f"## Committed: {commit_hash}")
    evidence.append(f"commit_hash:{commit_hash}")

    if push:
        push_result = _run_git(["push", "-u", remote, "HEAD"])
        if push_result.returncode == 0:
            details.append(f"## Pushed to {remote}")
            evidence.append(f"push_ok:{remote}")
        else:
            details.append(f"## Push failed: {push_result.stderr[:200]}")
            evidence.append(f"push_failed:{remote}")

    duration = (time.time() - t0) * 1000
    evidence.append(f"ship_duration:{duration:.0f}ms")

    return SkillResult(
        ok=True,
        skill="ship",
        summary=f"Shipped: {commit_hash} — {message[:60]}",
        details=details,
        evidence=evidence,
    )


def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=15,
    )


def _generate_message(status: str) -> str:
    lines = [l.strip() for l in status.strip().split("\n") if l.strip()]
    added = sum(1 for l in lines if l.startswith("A"))
    modified = sum(1 for l in lines if l.startswith("M"))
    deleted = sum(1 for l in lines if l.startswith("D"))

    parts = []
    if added:
        parts.append(f"add {added}")
    if modified:
        parts.append(f"update {modified}")
    if deleted:
        parts.append(f"remove {deleted}")

    return f"chore: {', '.join(parts) or 'update'} files"
