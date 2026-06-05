#!/usr/bin/env python3
"""Push to GitHub (origin) then Gitee mirror; alert on failure (GI-G-1)."""

from __future__ import annotations

import argparse
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
    run_git_remote_v,
)  # noqa: E402


def _push_remote(repo: Path, remote: str, refspec: str) -> tuple[bool, str]:
    cmd = ["git", "-C", str(repo), "push", remote, refspec]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, out[-500:]


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
    parser.add_argument("--notify", action="store_true", help="Telegram alert on failure")
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
    for name in names:
        ok, detail = _push_remote(repo, name, args.ref)
        if ok:
            print(f"OK: {name}")
        else:
            print(f"FAIL: {name}\n{detail}", file=sys.stderr)
            failures.append(f"{name}: {detail[:200]}")

    if failures and args.notify:
        try:
            import telegram_notify

            telegram_notify.notify_ops_event(
                "Git dual-remote push failed\n" + "\n".join(failures),
                level="critical",
            )
        except Exception as exc:
            print(f"[warn] telegram notification failed: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
