"""Gitee git mirror helpers (GI-G-0 / GI-G-1)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlparse, urlunparse

_OAUTH_RE = re.compile(r"oauth2:[^@]+@", re.IGNORECASE)
_TOKEN_IN_USER_RE = re.compile(r"^[^:/]+:[^@]+@")


def redact_remote_url(url: str) -> str:
    """Remove credentials from git remote URLs for logs and docs."""
    text = (url or "").strip()
    if not text:
        return ""
    text = _OAUTH_RE.sub("oauth2:***@", text)
    if "://" in text:
        scheme, rest = text.split("://", 1)
        if "@" in rest.split("/", 1)[0]:
            user_host, path = rest.split("@", 1)
            if ":" in user_host and not user_host.startswith("git@"):
                user = user_host.split(":", 1)[0]
                rest = f"{user}:***@{path}"
            text = f"{scheme}://{rest}"
    return text


def parse_git_remotes(output: str) -> dict[str, dict[str, str]]:
    """Parse `git remote -v` lines into {name: {fetch, push}}."""
    remotes: dict[str, dict[str, str]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] not in {"(fetch)", "(push)"}:
            continue
        name, url, kind = parts[0], parts[1], parts[2]
        key = "fetch" if kind == "(fetch)" else "push"
        remotes.setdefault(name, {})[key] = url
    return remotes


def classify_host(url: str) -> str:
    lowered = url.lower()
    if "gitee.com" in lowered:
        return "gitee"
    if "github.com" in lowered:
        return "github"
    host = urlparse(url).netloc.lower()
    return host or "unknown"


@dataclass(frozen=True)
class RemoteEntry:
    name: str
    fetch_url: str
    push_url: str
    host_kind: str

    @property
    def safe_fetch(self) -> str:
        return redact_remote_url(self.fetch_url)

    @property
    def safe_push(self) -> str:
        return redact_remote_url(self.push_url)


def build_remote_entries(remotes: dict[str, dict[str, str]]) -> list[RemoteEntry]:
    entries: list[RemoteEntry] = []
    for name in sorted(remotes):
        cfg = remotes[name]
        fetch_url = cfg.get("fetch", "")
        push_url = cfg.get("push", fetch_url)
        host_kind = classify_host(push_url or fetch_url)
        entries.append(
            RemoteEntry(name=name, fetch_url=fetch_url, push_url=push_url, host_kind=host_kind)
        )
    return entries


def mirror_status_from_output(output: str) -> dict[str, object]:
    remotes = parse_git_remotes(output)
    entries = build_remote_entries(remotes)
    hosts = {e.host_kind for e in entries}
    return {
        "remote_count": len(entries),
        "has_github": "github" in hosts,
        "has_gitee": "gitee" in hosts,
        "remotes": [
            {
                "name": e.name,
                "host": e.host_kind,
                "fetch": e.safe_fetch,
                "push": e.safe_push,
            }
            for e in entries
        ],
    }


def run_git_remote_v(
    repo: str | Path = "",
    *,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> tuple[int, str]:
    cmd = ["git", "-C", str(repo or Path.cwd()), "remote", "-v"]
    run = runner or subprocess.run
    proc = run(cmd, capture_output=True, text=True, check=False)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def collect_mirror_status(
    repo: str | Path = "",
    *,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> dict[str, object]:
    code, output = run_git_remote_v(repo, runner=runner)
    if code != 0:
        return {"ok": False, "error": output or f"git remote -v exit {code}"}
    status = mirror_status_from_output(output)
    status["ok"] = True
    return status


def default_push_remotes(entries: Sequence[RemoteEntry]) -> list[str]:
    """Prefer origin (GitHub) then explicit gitee remote."""
    names = [e.name for e in entries]
    ordered: list[str] = []
    if "origin" in names:
        ordered.append("origin")
    if "gitee" in names and "gitee" not in ordered:
        ordered.append("gitee")
    for name in names:
        if name not in ordered:
            ordered.append(name)
    return ordered


def remote_head_sha(
    push_url: str,
    branch: str = "HEAD",
    *,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> tuple[str, str]:
    """Return (sha, error) from git ls-remote for a branch ref."""
    ref = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    cmd = ["git", "ls-remote", push_url, ref]
    run = runner or subprocess.run
    proc = run(cmd, capture_output=True, text=True, check=False)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or out or f"exit {proc.returncode}").strip()
        return "", err[:200]
    if not out:
        return "", "empty ls-remote"
    line = out.splitlines()[0]
    sha = line.split()[0] if line.split() else ""
    return sha[:40], ""


def _resolve_branch(repo: str | Path, branch: str, runner: Callable[..., subprocess.CompletedProcess] | None) -> str:
    if branch and branch != "HEAD":
        return branch
    run = runner or subprocess.run
    proc = run(
        ["git", "-C", str(repo or Path.cwd()), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    name = (proc.stdout or "").strip()
    return name if proc.returncode == 0 and name and name != "HEAD" else "main"


def compare_mirror_heads(
    repo: str | Path = "",
    branch: str = "",
    *,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> dict[str, object]:
    """Compare GitHub origin vs Gitee push URL HEAD SHA."""
    code, output = run_git_remote_v(repo, runner=runner)
    if code != 0:
        return {"ok": False, "error": output or f"git remote -v exit {code}"}
    entries = build_remote_entries(parse_git_remotes(output))
    github_url = ""
    gitee_url = ""
    for entry in entries:
        for url in (entry.fetch_url, entry.push_url):
            if not url:
                continue
            host = classify_host(url)
            if host == "github" and not github_url:
                github_url = url
            if host == "gitee" and not gitee_url:
                gitee_url = url
    if not github_url or not gitee_url:
        return {
            "ok": False,
            "error": "missing github or gitee remote",
            "has_github": bool(github_url),
            "has_gitee": bool(gitee_url),
        }
    ref_branch = _resolve_branch(repo, branch or "HEAD", runner)
    gh_sha, gh_err = remote_head_sha(github_url, ref_branch, runner=runner)
    gt_sha, gt_err = remote_head_sha(gitee_url, ref_branch, runner=runner)
    if gh_err or gt_err:
        return {
            "ok": False,
            "error": gh_err or gt_err,
            "github_sha": gh_sha,
            "gitee_sha": gt_sha,
        }
    in_sync = gh_sha == gt_sha and bool(gh_sha)
    return {
        "ok": True,
        "branch": ref_branch,
        "github_sha": gh_sha,
        "gitee_sha": gt_sha,
        "in_sync": in_sync,
        "lag": 0 if in_sync else 1,
    }
