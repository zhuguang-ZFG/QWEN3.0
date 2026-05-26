#!/usr/bin/env python3
"""Deploy productivity slice: GFL-2 push translate + PE-D-1 search_gateway."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "telegram_push_translate.py",
    "search_gateway/dev_adapter.py",
    "search_gateway/searxng_adapter.py",
    "search_gateway/anysearch_adapter.py",
    "search_gateway/tinyfish_transport.py",
    "search_gateway/safety.py",
    "search_gateway/dev_tools.py",
    "lima_mcp/tools.py",
    "channel_gateway/channel_tools.py",
    "channel_gateway/integrations.py",
    "telegram_operator_tools.py",
]

ENV_LINES = (
    "TELEGRAM_PUSH_TRANSLATE_BACKEND=scnet_qwen30b,cf_llama70b",
)


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = 60) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return out


def _ensure_env_line(ssh: paramiko.SSHClient, key: str, value: str) -> None:
    _run(
        ssh,
        f"grep -q '^{key}=' {REMOTE}/.env 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={value}|' {REMOTE}/.env || "
        f"echo '{key}={value}' >> {REMOTE}/.env",
    )


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _run(ssh, f"mkdir -p {REMOTE}/search_gateway {REMOTE}/channel_gateway {REMOTE}/lima_mcp")

    for rel in FILES:
        local = base / rel
        if not local.is_file():
            ssh.close()
            sys.exit(f"missing {local}")
        sftp = ssh.open_sftp()
        sftp.put(str(local), f"{REMOTE}/{rel.replace(chr(92), '/')}")
        sftp.close()
        print(f"uploaded {rel}")

    for line in ENV_LINES:
        key, value = line.split("=", 1)
        _ensure_env_line(ssh, key, value)
        print(f"env {key}={value}")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)
    active = _run(ssh, "systemctl is-active lima-router").strip()
    verify = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 -c "
        "\"import telegram_push_translate as t; print(','.join(t.push_translate_backends()))\"",
    )
    print(f"service={active} translate_backends={verify}")
    ok = active == "active" and verify.startswith("scnet_qwen30b")
    print("deploy_productivity_slice_ok" if ok else "deploy_productivity_slice_FAILED")
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
