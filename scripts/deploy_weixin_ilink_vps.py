#!/usr/bin/env python3
"""Deploy LiMa Weixin iLink bridge to VPS (systemd, localhost channel)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SERVICE = "lima-weixin-ilink"


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = 120) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return (out + ("\n" + err if err.strip() else "")).strip()


def main() -> None:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    bridge = base / "scripts" / "hermes_weixin_lima_bridge.py"
    accounts = Path.home() / ".hermes" / "weixin" / "accounts"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    print("=== 1. deps (hermes gateway + aiohttp) ===")
    print(
        _run(
            ssh,
            '/usr/local/bin/python3.10 -m pip install -q "hermes-agent[messaging]" '
            "aiohttp cryptography 2>/dev/null || "
            "/usr/local/bin/python3.10 -m pip install -q aiohttp cryptography",
        )
    )

    print("=== 2. upload bridge + wechat_bridge ===")
    sftp = ssh.open_sftp()
    try:
        sftp.mkdir(f"{REMOTE}/wechat_bridge")
    except OSError:
        pass
    sftp.put(str(bridge), f"{REMOTE}/scripts/hermes_weixin_lima_bridge.py")
    for rel in (
        "__init__.py",
        "lima_client.py",
        "weixin_inbound.py",
        "typing_helper.py",
        "weixin_outbound.py",
        "invite_qr.py",
    ):
        local = base / "wechat_bridge" / rel
        if local.is_file():
            sftp.put(str(local), f"{REMOTE}/wechat_bridge/{rel}")
            print(f"  wechat_bridge/{rel}")
    remote_acct = "/root/.hermes/weixin/accounts"
    _run(ssh, f"mkdir -p {remote_acct}")
    for f in accounts.glob("*.json"):
        if "context" in f.name or "sync" in f.name:
            continue
        sftp.put(str(f), f"{remote_acct}/{f.name}")
        print(f"  account {f.name}")
    sftp.close()

    print("=== 3. env snippet (merge WEIXIN_* into .env manually if needed) ===")
    acc = next((p for p in accounts.glob("*.json") if "context" not in p.name and "sync" not in p.name), None)
    if acc:
        import json

        data = json.loads(acc.read_text(encoding="utf-8"))
        aid = acc.stem
        lines = [
            f"WEIXIN_ACCOUNT_ID={aid}",
            f"WEIXIN_TOKEN={data.get('token', '')}",
            f"WEIXIN_BASE_URL={data.get('base_url', 'https://ilinkai.weixin.qq.com')}",
            "WEIXIN_DM_POLICY=open",
            "WEIXIN_GROUP_POLICY=disabled",
            "LIMA_CHANNEL_BASE_URL=http://127.0.0.1:8080",
        ]
        patch = "\n".join(lines) + "\n"
        sftp = ssh.open_sftp()
        with sftp.file(f"{REMOTE}/data/weixin_ilink.env.snippet", "w") as fh:
            fh.write(patch)
        sftp.close()
        print(f"  wrote {REMOTE}/data/weixin_ilink.env.snippet — append to .env on VPS")

    unit = f"""[Unit]
Description=LiMa Weixin iLink bridge
After=network.target lima-router.service
Wants=lima-router.service

[Service]
Type=simple
WorkingDirectory={REMOTE}
Environment=LIMA_CHANNEL_BASE_URL=http://127.0.0.1:8080
Environment=HERMES_HOME=/root/.hermes
EnvironmentFile=-{REMOTE}/.env
ExecStart=/usr/local/bin/python3.10 {REMOTE}/scripts/hermes_weixin_ilima_bridge.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    sftp = ssh.open_sftp()
    with sftp.file(f"/etc/systemd/system/{SERVICE}.service", "w") as fh:
        fh.write(unit)
    sftp.close()

    print("=== 4. systemd ===")
    print(_run(ssh, "systemctl daemon-reload && systemctl enable " + SERVICE))
    print(_run(ssh, "systemctl restart " + SERVICE))
    print(_run(ssh, "systemctl is-active " + SERVICE))
    print(_run(ssh, f"journalctl -u {SERVICE} -n 15 --no-pager"))
    ssh.close()
    print("done — merge weixin_ilink.env.snippet into /opt/lima-router/.env if token not in .env yet")


if __name__ == "__main__":
    main()
