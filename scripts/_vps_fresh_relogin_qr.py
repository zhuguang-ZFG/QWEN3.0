#!/usr/bin/env python3
"""Restart bridge and return fresh iLink relogin URL from VPS."""
import json
import os
import re
import time

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"
STATUS = "/opt/lima-router/data/weixin_relogin_status.json"
HTML = "/opt/lima-router/data/weixin_relogin_qr.html"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 60) -> str:
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)

    print("Restarting lima-weixin-ilink...")
    print(run(ssh, "systemctl restart lima-weixin-ilink && sleep 3 && systemctl is-active lima-weixin-ilink"))

    url = ""
    phase = ""
    for _ in range(24):
        raw = run(ssh, f"cat {STATUS} 2>/dev/null || echo '{{}}'")
        try:
            st = json.loads(raw)
        except json.JSONDecodeError:
            st = {}
        phase = str(st.get("phase") or "")
        url = str(st.get("url") or "")
        if phase == "ok":
            print("RELOGIN_ALREADY_OK", st.get("account_id", ""))
            ssh.close()
            return
        if phase == "waiting_scan" and url.startswith("https://"):
            break
        time.sleep(2)

    if not url:
        html = run(ssh, f"grep -oP 'https://liteapp[^\"]+' {HTML} 2>/dev/null | head -1")
        url = html.replace("&amp;", "&") if html else ""

    if not url:
        log_tail = run(ssh, "journalctl -u lima-weixin-ilink -n 30 --no-pager 2>/dev/null")
        m = re.search(r"https://liteapp\.weixin\.qq\.com/[^\s)]+", log_tail)
        if m:
            url = m.group(0).rstrip("&b")

    print("\n=== FRESH_RELOGIN_URL ===")
    print(url or "(still generating, retry in 10s)")
    print("\n=== phase ===", phase or "unknown")
    if url:
        print("\n=== status json ===")
        print(run(ssh, f"cat {STATUS} 2>/dev/null"))
    ssh.close()


if __name__ == "__main__":
    main()
