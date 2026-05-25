#!/usr/bin/env python3
"""Deploy LiMa Weixin iLink bridge to VPS (systemd, localhost channel)."""

from __future__ import annotations

import os
import sys
import time
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

    req = base / "requirements-weixin-ilink.txt"
    sftp = ssh.open_sftp()
    sftp.put(str(req), f"{REMOTE}/requirements-weixin-ilink.txt")
    sftp.close()
    PY = "/usr/bin/python3.11"
    PIP = f"{PY} -m pip"

    print("=== 1. Python 3.11 (hermes-agent requires >=3.11) ===")
    print(
        _run(
            ssh,
            "dnf install -y python3.11 python3.11-pip python3.11-devel gcc 2>/dev/null || "
            "yum install -y python3.11 python3.11-pip python3.11-devel gcc",
            timeout=300,
        )
    )
    print(_run(ssh, f"test -x {PY} && {PY} --version"))

    print("=== 2. deps (iLink transport only, no [messaging] extras) ===")
    print(_run(ssh, f"{PIP} install -q -r {REMOTE}/requirements-weixin-ilink.txt", timeout=300))

    print("=== 3. upload bridge + wechat_bridge ===")
    sftp = ssh.open_sftp()
    _run(ssh, f"mkdir -p {REMOTE}/scripts {REMOTE}/wechat_bridge")
    try:
        sftp.mkdir(f"{REMOTE}/wechat_bridge")
    except OSError:
        pass
    sftp.put(str(bridge), f"{REMOTE}/scripts/hermes_weixin_lima_bridge.py")
    mimo_tts = base / "mimo_tts.py"
    if mimo_tts.is_file():
        sftp.put(str(mimo_tts), f"{REMOTE}/mimo_tts.py")
        print("  mimo_tts.py")
    qr_login = base / "scripts" / "hermes_weixin_qr_login.py"
    if qr_login.is_file():
        sftp.put(str(qr_login), f"{REMOTE}/scripts/hermes_weixin_qr_login.py")
        print("  scripts/hermes_weixin_qr_login.py")
    print(f"  scripts/hermes_weixin_lima_bridge.py")
    for rel in (
        "__init__.py",
        "lima_client.py",
        "weixin_inbound.py",
        "typing_helper.py",
        "weixin_outbound.py",
        "invite_qr.py",
        "ilink_session.py",
        "voice_silk.py",
        "weixin_adapter.py",
        "context_tokens.py",
        "weixin_voice_send.py",
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
    share_json = base / "data" / "weixin_share_qr.json"
    if share_json.is_file():
        _run(ssh, f"mkdir -p {REMOTE}/data")
        sftp.put(str(share_json), f"{REMOTE}/data/weixin_share_qr.json")
        print("  data/weixin_share_qr.json")
    sftp.close()

    print("=== 4. env snippet ===")
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
            "LIMA_WEIXIN_AUTO_RELOGIN=1",
            "LIMA_WEIXIN_KEEPALIVE_MIN=18",
        ]
        patch = "\n".join(lines) + "\n"
        sftp = ssh.open_sftp()
        with sftp.file(f"{REMOTE}/data/weixin_ilink.env.snippet", "w") as fh:
            fh.write(patch)
        sftp.close()
        print(f"  wrote {REMOTE}/data/weixin_ilink.env.snippet — append to .env on VPS")

    unit = f"""[Unit]
Description=LiMa Weixin iLink bridge (transport only, LiMa /channel brain)
After=network.target lima-router.service
Wants=lima-router.service

[Service]
Type=simple
WorkingDirectory={REMOTE}
Environment=LIMA_CHANNEL_BASE_URL=http://127.0.0.1:8080
Environment=LIMA_WEIXIN_VPS=1
Environment=HERMES_HOME=/root/.hermes
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile=-{REMOTE}/.env
ExecStart=/usr/bin/python3.11 {REMOTE}/scripts/hermes_weixin_lima_bridge.py
Restart=on-failure
RestartSec=15
MemoryMax=384M
CPUQuota=40%

[Install]
WantedBy=multi-user.target
"""
    sftp = ssh.open_sftp()
    with sftp.file(f"/etc/systemd/system/{SERVICE}.service", "w") as fh:
        fh.write(unit)
    sftp.close()

    print("=== 5. merge weixin env into .env ===")
    sftp = ssh.open_sftp()
    sftp.put(
        str(base / "scripts" / "_merge_weixin_ilink_env_remote.py"),
        f"{REMOTE}/_merge_weixin_ilink_env.py",
    )
    sftp.close()
    print(_run(ssh, f"cd {REMOTE} && python3.10 _merge_weixin_ilink_env.py && rm -f _merge_weixin_ilink_env.py"))

    print("=== 6. stop local duplicate (hint) ===")
    print("Run on Windows: scripts/stop_weixin_lima_ilink.ps1 — only one iLink poller per account")

    print("=== 7. systemd ===")
    print(_run(ssh, "systemctl daemon-reload && systemctl enable " + SERVICE))
    print(_run(ssh, "systemctl restart " + SERVICE))
    time.sleep(4)
    print(_run(ssh, "systemctl is-active " + SERVICE))
    print(_run(ssh, f"journalctl -u {SERVICE} -n 20 --no-pager"))
    ssh.close()
    print("done — VPS iLink bridge only; Hermes gateway/agent not installed")


if __name__ == "__main__":
    main()
