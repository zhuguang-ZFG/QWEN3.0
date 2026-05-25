#!/usr/bin/env python3
"""Set MIMO_TTS_KEY on VPS .env (do not commit). Usage: python patch_mimo_key_vps.py <key>"""
from __future__ import annotations

import os
import sys
import time

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY_PATH = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python patch_mimo_key_vps.py <MIMO_TTS_KEY>")
        return 1
    mimo_key = sys.argv[1].strip()

    remote_py = f'''from pathlib import Path
p = Path("{REMOTE}/.env")
lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
keys = ("MIMO_TTS_KEY", "MIMO_API_KEY")
out, seen = [], set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in keys:
            out.append(f"{{k}}={mimo_key!r}")
            seen.add(k)
        else:
            out.append(line)
    else:
        out.append(line)
for k in keys:
    if k not in seen:
        out.append(f"{{k}}={mimo_key!r}")
p.write_text("\\n".join(out) + "\\n", encoding="utf-8")
print("mimo_key_set")
'''.replace("{mimo_key!r}", repr(mimo_key))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY_PATH, timeout=60)
    sftp = ssh.open_sftp()
    sftp.file(f"{REMOTE}/_patch_mimo_key.py", "w").write(remote_py.encode("utf-8"))
    sftp.close()
    _i, o, e = ssh.exec_command(
        f"cd {REMOTE} && /usr/local/bin/python3.10 _patch_mimo_key.py && rm -f _patch_mimo_key.py",
        timeout=30,
    )
    print(o.read().decode(), e.read().decode())
    ssh.exec_command("systemctl restart lima-router")
    time.sleep(8)
    active = ssh.exec_command("systemctl is-active lima-router")[1].read().decode().strip()
    print("lima-router:", active)
    check = ssh.exec_command(
        f"grep '^MIMO_TTS_KEY=' {REMOTE}/.env | cut -d= -f1"
    )[1].read().decode().strip()
    print("env:", check or "missing")
    ssh.close()
    return 0 if active == "active" and check else 1


if __name__ == "__main__":
    raise SystemExit(main())
