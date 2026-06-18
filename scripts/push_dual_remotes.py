#!/usr/bin/env python3
"""Push to GitHub (origin) then Gitee mirror; report failures to stderr."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from gitee_mirror import (
    build_remote_entries,
    default_push_remotes,
    parse_git_remotes,
    redact_remote_url,
    run_git_remote_v,
)  # noqa: E402


def _push_remote(repo: Path, remote: str, refspec: str) -> tuple[bool, str]:
    cmd = ["git", "-C", str(repo), "push", remote, refspec]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, out[-500:]


def _gitee_token() -> str:
    """Return Gitee personal access token from environment, preferring GITEE_TOKEN."""
    return os.environ.get("GITEE_TOKEN", "").strip() or os.environ.get("GITEE_ACCESS_TOKEN", "").strip()


def _gitee_https_push_url(base_url: str, token: str) -> str:
    """Convert a Gitee SSH or HTTPS URL into an HTTPS URL with oauth2 token."""
    if base_url.startswith("git@gitee.com:"):
        repo_path = base_url[len("git@gitee.com:") :]
        return f"https://oauth2:{token}@gitee.com/{repo_path}"
    lowered = base_url.lower()
    if "gitee.com" not in lowered or "://" not in base_url:
        return ""
    scheme, rest = base_url.split("://", 1)
    # Strip any existing credentials from the netloc portion.
    netloc_path = rest
    if "@" in netloc_path.split("/", 1)[0]:
        _, netloc_path = netloc_path.split("@", 1)
    return f"{scheme}://oauth2:{token}@{netloc_path}"


def _check_gitee_ssh(repo: Path, entries: list) -> tuple[bool, str]:
    """Return (ok, message). If gitee uses SSH, verify the key is accepted."""
    gitee_entry = next((e for e in entries if e.name == "gitee"), None)
    gitee_url = gitee_entry.push_url if gitee_entry else ""
    if not gitee_url.startswith("git@gitee.com:"):
        return True, "gitee is not using SSH"
    proc = subprocess.run(
        ["ssh", "-T", "git@gitee.com"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if proc.returncode == 0:
        return True, ""
    detail = (proc.stdout or "") + (proc.stderr or "")
    pub_key = Path.home() / ".ssh" / "id_ed25519.pub"
    if not pub_key.exists():
        pub_key = Path.home() / ".ssh" / "id_rsa.pub"
    key_hint = f"\nPublic key to add to Gitee: {pub_key}\n{pub_key.read_text().strip() if pub_key.exists() else '(not found)'}"
    return False, (
        f"Gitee SSH authentication failed.{key_hint}\n"
        "Add the key at https://gitee.com/profile/sshkeys "
        "or set GITEE_TOKEN / GITEE_ACCESS_TOKEN for HTTPS fallback.\n"
        f"Underlying error: {detail.strip()[:300]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--ref", default="HEAD", help="Ref to push (default HEAD → current branch)")
    parser.add_argument(
        "--remotes",
        default="",
        help="Comma-separated remote names (default: origin,gitee)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--notify", action="store_true", help="Print failure summary to stderr")
    args = parser.parse_args()

    repo = Path(args.repo)
    code, output = run_git_remote_v(repo)
    if code != 0:
        print(output or f"git remote -v exit {code}", file=sys.stderr)
        return 1

    entries = build_remote_entries(parse_git_remotes(output))
    if args.remotes.strip():
        names = [n.strip() for n in args.remotes.split(",") if n.strip()]
    else:
        names = default_push_remotes(entries)

    if args.dry_run:
        print(f"would push {args.ref} to: {', '.join(names)}")
        return 0

    failures: list[str] = []
    if "gitee" in names:
        ssh_ok, ssh_detail = _check_gitee_ssh(repo, entries)
        if not ssh_ok:
            token = _gitee_token()
            gitee_entry = next((e for e in entries if e.name == "gitee"), None)
            base_url = (gitee_entry.push_url if gitee_entry else "").strip()
            https_url = _gitee_https_push_url(base_url, token) if token and base_url else ""
            if https_url:
                safe_url = redact_remote_url(https_url)
                ok, detail = _push_remote(repo, https_url, args.ref)
                if ok:
                    print(f"OK: gitee (HTTPS fallback via {safe_url})")
                else:
                    print(
                        f"FAIL: gitee (HTTPS fallback via {safe_url})\n{detail}",
                        file=sys.stderr,
                    )
                    failures.append(f"gitee: {detail[:200]}")
            else:
                print(f"FAIL: gitee\n{ssh_detail}", file=sys.stderr)
                failures.append(f"gitee: {ssh_detail[:200]}")
            names = [n for n in names if n != "gitee"]

    for name in names:
        ok, detail = _push_remote(repo, name, args.ref)
        if ok:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name}\n{detail}", file=sys.stderr)
            failures.append(f"{name}: {detail[:200]}")

    if failures and args.notify:
        print("Git dual-remote push failed\n" + "\n".join(failures), file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
