#!/usr/bin/env python3
"""Set GitHub Actions variable HEALTHCHECK_LIMA_VPS_URL from local .env (INF-B)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REPO = os.environ.get("GITHUB_REPOSITORY", "zhuguang-ZFG/QWEN3.0")


def main() -> int:
    load_dotenv(ROOT / ".env")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    ping_url = os.environ.get("HEALTHCHECK_LIMA_VPS_URL", "").strip().rstrip("/")
    if not token:
        print("sync_github_healthcheck_var_SKIP no GITHUB_TOKEN")
        return 0
    if not ping_url:
        print("sync_github_healthcheck_var_SKIP no HEALTHCHECK_LIMA_VPS_URL")
        return 0

    owner, name = REPO.split("/", 1)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{owner}/{name}/actions/variables/HEALTHCHECK_LIMA_VPS_URL"
    body = {"name": "HEALTHCHECK_LIMA_VPS_URL", "value": ping_url}
    with httpx.Client(timeout=20.0) as client:
        get_resp = client.get(url, headers=headers)
        if get_resp.status_code == 404:
            resp = client.post(
                f"https://api.github.com/repos/{owner}/{name}/actions/variables",
                headers=headers,
                json=body,
            )
        else:
            resp = client.patch(url, headers=headers, json={"value": ping_url})

    if resp.status_code >= 400:
        print(f"sync_github_healthcheck_var_FAILED status={resp.status_code} body={resp.text[:200]}")
        return 1
    print("sync_github_healthcheck_var_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
