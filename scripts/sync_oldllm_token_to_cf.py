#!/usr/bin/env python3
"""Push latest TheOldLLM token from Windows oldllm_proxy → Cloudflare Worker."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_NODE_SCRIPT = Path("D:/ollama_server/sync_oldllm_token_to_cf.js")
GIT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--script",
        type=Path,
        default=DEFAULT_NODE_SCRIPT,
        help="Path to sync_oldllm_token_to_cf.js",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Playwright CDP capture before push",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After push, GET upstream /v1/models",
    )
    parser.add_argument(
        "--diag",
        action="store_true",
        help="Run diag_oldllm_proxy.py after sync",
    )
    parser.add_argument(
        "--restart-proxy",
        action="store_true",
        help="Restart oldllm_proxy after push (loads theoldllm_token.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions only",
    )
    args = parser.parse_args()

    if not args.script.is_file():
        print(f"missing script: {args.script}", file=sys.stderr)
        return 1
    if not (os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")):
        interactive = Path("D:/ollama_server/refresh_token_interactive.js")
        if interactive.is_file():
            text = interactive.read_text(encoding="utf-8", errors="replace")
            import re

            m = re.search(r"CF_API_TOKEN = '([^']+)'", text)
            if m:
                os.environ.setdefault("CLOUDFLARE_API_TOKEN", m.group(1))
        if not (os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")):
            print(
                "Set CLOUDFLARE_API_TOKEN or CF_API_TOKEN (or keep refresh_token_interactive.js)",
                file=sys.stderr,
            )
            return 1

    node_args = ["node", str(args.script)]
    if args.capture:
        node_args.append("--capture")
    if args.verify or args.diag:
        node_args.append("--verify")
    if args.restart_proxy:
        node_args.append("--restart-proxy")
    if args.dry_run:
        node_args.append("--dry-run")

    print("Running:", " ".join(node_args[:3]), "...")
    proc = subprocess.run(node_args, cwd=str(args.script.parent))
    if proc.returncode != 0:
        return proc.returncode

    if args.diag and not args.dry_run:
        diag = GIT_ROOT / "scripts" / "diag_oldllm_proxy.py"
        if diag.is_file():
            return subprocess.call([sys.executable, str(diag)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
