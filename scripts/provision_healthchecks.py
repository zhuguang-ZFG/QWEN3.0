#!/usr/bin/env python3
"""Provision Healthchecks.io check and deploy VPS dead-man (INF-B)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import healthchecks_io as hio  # noqa: E402


def _append_env(key: str, value: str) -> None:
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines() if env_path.exists() else []
    out: list[str] = []
    replaced = False
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("HEALTHCHECKS_API_KEY", "").strip()
    ping_key = os.environ.get("HEALTHCHECKS_PING_KEY", "").strip()
    ping_url = os.environ.get("HEALTHCHECK_LIMA_VPS_URL", "").strip()

    resolved, detail = hio.resolve_vps_router_ping_url(
        ping_url=ping_url,
        api_key=api_key,
        ping_key=ping_key,
    )
    print(f"resolve={detail}")
    if not resolved:
        print("provision_healthchecks_SKIP set HEALTHCHECKS_API_KEY or HEALTHCHECKS_PING_KEY or HEALTHCHECK_LIMA_VPS_URL")
        return 2

    _append_env("HEALTHCHECK_LIMA_VPS_URL", resolved)
    os.environ["HEALTHCHECK_LIMA_VPS_URL"] = resolved
    print(f"local .env HEALTHCHECK_LIMA_VPS_URL updated (len={len(resolved)})")

    import subprocess

    steps = [
        [sys.executable, str(ROOT / "scripts" / "sync_github_healthcheck_var.py")],
        [sys.executable, str(ROOT / "scripts" / "deploy_healthchecks_vps.py")],
    ]
    for cmd in steps:
        proc = subprocess.run(cmd, cwd=ROOT)
        if proc.returncode != 0:
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
