#!/usr/bin/env python3
"""Deploy INF-B Healthchecks dead-man: VPS cron + env + smoke ping."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import healthcheck_ping as hc  # noqa: E402
import healthchecks_io as hio  # noqa: E402

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
CRON_FILE = "/etc/cron.d/lima-router-healthcheck"
LOG_FILE = "/var/log/lima-healthcheck.log"

FILES = [
    "healthcheck_ping.py",
    "healthchecks_io.py",
    "scripts/healthcheck_ping.py",
    "scripts/vps_router_healthcheck.sh",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 60) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out


def _upsert_env(ssh: paramiko.SSHClient, key: str, value: str) -> None:
    escaped = value.replace("'", "'\"'\"'")
    _run(
        ssh,
        f"grep -q '^{key}=' {REMOTE}/.env 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={escaped}|' {REMOTE}/.env || "
        f"echo '{key}={escaped}' >> {REMOTE}/.env",
    )


def _install_cron(ssh: paramiko.SSHClient) -> None:
    body = (
        "# LiMa VPS router dead-man (INF-B)\n"
        "SHELL=/bin/bash\n"
        "*/5 * * * * root "
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a && "
        f"LIMA_HEALTHCHECK_ENABLED=1 ./scripts/vps_router_healthcheck.sh "
        f">> {LOG_FILE} 2>&1\n"
    )
    sftp = ssh.open_sftp()
    with sftp.file(CRON_FILE, "w") as fh:
        fh.write(body)
    sftp.close()
    _run(ssh, f"chmod 644 {CRON_FILE}")


def _github_var(name: str) -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "zhuguang-ZFG/QWEN3.0")
    if not token:
        return ""
    owner, repo_name = repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/variables/{name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code >= 400:
            return ""
        return str(resp.json().get("value") or "").strip()
    except httpx.HTTPError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ping-url", default="", help="Healthchecks ping URL")
    parser.add_argument("--api-key", default="", help="Healthchecks Management API key")
    parser.add_argument("--ping-key", default="", help="Healthchecks project ping key (slug mode)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    ping_url = (
        args.ping_url
        or os.environ.get("HEALTHCHECK_LIMA_VPS_URL", "")
        or _github_var("HEALTHCHECK_LIMA_VPS_URL")
    )
    api_key = args.api_key or os.environ.get("HEALTHCHECKS_API_KEY", "")
    ping_key = args.ping_key or os.environ.get("HEALTHCHECKS_PING_KEY", "")

    resolved, detail = hio.resolve_vps_router_ping_url(
        ping_url=ping_url,
        api_key=api_key,
        ping_key=ping_key,
    )
    print(f"resolve={detail}")
    if not resolved:
        print("deploy_healthchecks_FAILED missing ping url (set HEALTHCHECK_LIMA_VPS_URL or HEALTHCHECKS_API_KEY or HEALTHCHECKS_PING_KEY in .env)")
        return 2

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    _run(ssh, f"mkdir -p {REMOTE}/scripts")
    sftp = ssh.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    _run(ssh, f"chmod +x {REMOTE}/scripts/vps_router_healthcheck.sh")
    _upsert_env(ssh, "HEALTHCHECK_LIMA_VPS_URL", resolved)
    _upsert_env(ssh, "LIMA_HEALTHCHECK_ENABLED", "1")
    _install_cron(ssh)
    print(f"installed {CRON_FILE}")

    code, smoke = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 scripts/healthcheck_ping.py --force "
        f"--env-key HEALTHCHECK_LIMA_VPS_URL --check http://127.0.0.1:8080/health",
    )
    print(f"smoke_exit={code} {smoke}")

    _, cron_run = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"LIMA_HEALTHCHECK_ENABLED=1 ./scripts/vps_router_healthcheck.sh",
    )
    print(f"cron_script={cron_run}")

    ssh.close()
    ok = code == hc.EXIT_OK
    print("deploy_healthchecks_ok" if ok else "deploy_healthchecks_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
