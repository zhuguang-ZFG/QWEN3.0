#!/usr/bin/env python3
"""Verify iLink session healthy after relogin."""
import json
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"


def run(cmd: str) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    _, o, e = ssh.exec_command(cmd, timeout=60)
    out = (o.read() + e.read()).decode(errors="replace").strip()
    ssh.close()
    return out


def main() -> None:
    status_raw = run("cat /opt/lima-router/data/weixin_relogin_status.json 2>/dev/null || echo {}")
    try:
        st = json.loads(status_raw)
    except json.JSONDecodeError:
        st = {}
    print("relogin_status:", json.dumps(st, ensure_ascii=False))

    logs = run(
        "journalctl -u lima-weixin-ilink -n 40 --no-pager 2>/dev/null | "
        "grep -E 'relogin OK|credentials reloaded|session dead|errcode=-14|scan QR|msgs|LiMa reply|voice' | tail -20"
    )
    print("\nkey_logs:\n", logs or "(none)")

    ok = st.get("phase") == "ok" or "relogin OK" in logs or "credentials reloaded" in logs
    dead = "errcode=-14" in logs and "relogin OK" not in logs
    print("\nVERDICT:", "OK" if ok and not dead else ("STILL_DEAD" if dead else "CHECK"))


if __name__ == "__main__":
    main()
