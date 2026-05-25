#!/usr/bin/env python3
"""Deep diag: guest inbound -> channel -> outbound on VPS."""
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"


def run(cmd: str, t: int = 90) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    _, o, e = ssh.exec_command(cmd, timeout=t)
    out = (o.read() + e.read()).decode(errors="replace").strip()
    ssh.close()
    return out


def main() -> None:
    cmds = [
        ("services", "systemctl is-active lima-weixin-ilink lima-router"),
        ("account", "ls -la /root/.hermes/weixin/accounts/*.json 2>/dev/null | grep -v context | grep -v sync | grep -v archive"),
        ("share_qr", "cat /opt/lima-router/data/weixin_share_qr.json 2>/dev/null"),
        ("weixin_env", "grep '^WEIXIN_ACCOUNT_ID=' /opt/lima-router/.env"),
        ("bridge_inbound", "journalctl -u lima-weixin-ilink --since '3 hours ago' --no-pager 2>/dev/null | grep 'inbound from=' | tail -30"),
        ("bridge_reply", "journalctl -u lima-weixin-ilink --since '3 hours ago' --no-pager 2>/dev/null | grep -E 'replied|HTTP|error|send_|failed|exception' | tail -35"),
        ("bridge_all_recent", "journalctl -u lima-weixin-ilink --since '45 min ago' --no-pager 2>/dev/null | tail -50"),
        ("router_wechat", "journalctl -u lima-router --since '3 hours ago' --no-pager 2>/dev/null | grep 'wechat/message' | tail -25"),
        ("channel_db", "python3.10 -c \"import sqlite3,os;p=os.environ.get('LIMA_CHANNEL_DB_PATH','/opt/lima-router/data/channel_bindings.db');c=sqlite3.connect(p);r=c.execute('select channel_user_id_hash,role,status,created_at from channel_bindings order by created_at desc limit 15').fetchall();print('bindings',len(r));[print(x) for x in r]\" 2>&1"),
        ("sidecar_set", "grep -c '^LIMA_WECHAT_SIDECAR_TOKEN=.' /opt/lima-router/.env"),
        ("smoke", "cd /opt/lima-router && python3.10 scripts/_vps_fake_wechat_smoke_remote.py 2>&1 | tail -20"),
    ]
    for name, cmd in cmds:
        print(f"\n=== {name} ===")
        print(run(cmd) or "(empty)")


if __name__ == "__main__":
    main()
