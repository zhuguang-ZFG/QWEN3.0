"""Generate review-brief.md from git state (works in any repo)."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from lima_mcp_stdio.multi_cli.scope import resolve_scope

GENERIC_REDFLAGS = """
- No silent degradation (`except Exception: pass` without log)
- No hardcoded secrets in tracked files
- Prefer small focused modules; flag god files and missing tests for critical paths
""".strip()


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return ""
    if proc.returncode != 0:
        return proc.stderr.strip() or proc.stdout.strip()
    return proc.stdout.strip()


def _changed_files(cwd: Path) -> list[str]:
    unstaged = _run_git(["diff", "--name-only"], cwd)
    staged = _run_git(["diff", "--cached", "--name-only"], cwd)
    names = {line.strip() for line in (unstaged + "\n" + staged).splitlines() if line.strip()}
    return sorted(names)


def _diff_stat(cwd: Path) -> str:
    stat = _run_git(["diff", "--stat"], cwd)
    staged = _run_git(["diff", "--cached", "--stat"], cwd)
    parts = [p for p in (stat, staged) if p]
    return "\n\n".join(parts) if parts else "(no unstaged/staged diff)"


def _diff_unified(cwd: Path, max_lines: int = 400) -> str:
    diff = _run_git(["diff", "-U3"], cwd)
    staged = _run_git(["diff", "--cached", "-U3"], cwd)
    merged = "\n".join(p for p in (diff, staged) if p).strip()
    if not merged:
        return "(no diff hunks)"
    lines = merged.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n\n... truncated {len(lines) - max_lines} lines ..."
    return merged


def _project_redflags(project_root: Path) -> str:
    for name in ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"):
        path = project_root / name
        if path.is_file():
            return f"See `{name}` in repo root for project-specific rules.\n\n{GENERIC_REDFLAGS}"
    return GENERIC_REDFLAGS


def _scope_files(task: str, scope: str | None, project_root: Path) -> list[str]:
    files = _changed_files(project_root)
    effective_scope = resolve_scope(task, scope, project_root)
    if effective_scope:
        return [effective_scope]
    if files:
        return files
    return ["(mention a file path in task or pass scope)"]


def _header_section(task: str, project_root: Path, scope_files: list[str]) -> list[str]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = _run_git(["rev-parse", "--short", "HEAD"], project_root) or "unknown"
    lines = [
        "# MiMo MCP Review Brief",
        "",
        f"- generated_at: {now}",
        f"- git_head: {head}",
        f"- task: {task}",
        "",
        "## Scope",
        "",
    ]
    lines.extend(f"- `{item}`" for item in scope_files)
    return lines


def _changed_files_section(files: list[str]) -> list[str]:
    lines = ["", "## Changed files", ""]
    if files:
        lines.extend(f"- `{item}`" for item in files)
    else:
        lines.append("- (none)")
    return lines


def _diff_section(project_root: Path) -> list[str]:
    return [
        "",
        "## diff --stat",
        "",
        "```",
        _diff_stat(project_root),
        "```",
        "",
        "## diff excerpt",
        "",
        "```diff",
        _diff_unified(project_root),
        "```",
        "",
    ]


def _footer_section(project_root: Path) -> list[str]:
    return [
        "## Review red flags",
        "",
        _project_redflags(project_root),
        "",
        "## JSON output contract",
        "",
        "Append JSON array of findings with evidence (P0-P3).",
        "",
    ]


def generate_brief(project_root: Path, task: str, scope: str | None = None) -> str:
    files = _changed_files(project_root)
    scope_files = _scope_files(task, scope, project_root)
    sections = [
        *_header_section(task, project_root, scope_files),
        *_changed_files_section(files),
        *_diff_section(project_root),
        *_footer_section(project_root),
    ]
    return "\n".join(sections)


def write_brief(project_root: Path, artifact_dir: Path, task: str, scope: str | None = None) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "review-brief.md"
    path.write_text(generate_brief(project_root, task, scope), encoding="utf-8")
    return path
