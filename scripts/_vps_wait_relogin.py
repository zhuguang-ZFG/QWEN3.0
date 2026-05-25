#!/usr/bin/env python3
"""Poll VPS until iLink relogin phase=ok or timeout."""
import json
import os
import sys
import time

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"
PATH = "/opt/lima-router/data/weixin_relogin_status.json"


def read_status() -> dict:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    _, o, _ = ssh.exec_command(f"cat {PATH} 2>/dev/null", timeout=20)
    raw = o.read().decode(errors="replace").strip()
    ssh.close()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def main() -> int:
    deadline = time.time() + int(sys.argv[1]) if len(sys.argv) > 1 else time.time() + 300
    last_phase = ""
    while time.time() < deadline:
        st = read_status()
        phase = str(st.get("phase") or "")
        if phase != last_phase:
            print(json.dumps(st, ensure_ascii=False, indent=2))
            last_phase = phase
        if phase == "ok":
            print("RELOGIN_OK", st.get("account_id", ""))
            return 0
        if phase == "error":
            print("RELOGIN_ERROR", st.get("msg", ""))
            return 2
        time.sleep(5)
    print("RELOGIN_TIMEOUT still", last_phase or "unknown")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
