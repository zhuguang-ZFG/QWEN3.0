#!/usr/bin/env python3
"""Set LIMA_WEIXIN_KEEPALIVE_MIN on VPS systemd override."""
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"
DROPIN = "/etc/systemd/system/lima-weixin-ilink.service.d/override.conf"
def main() -> None:
    body = """[Service]
Environment=LIMA_WEIXIN_KEEPALIVE_MIN=10
"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    ssh.exec_command("mkdir -p /etc/systemd/system/lima-weixin-ilink.service.d", timeout=15)
    sftp = ssh.open_sftp()
    with sftp.file(DROPIN, "w") as f:
        f.write(body)
    sftp.close()
    _, o, e = ssh.exec_command("systemctl daemon-reload", timeout=30)
    print((o.read() + e.read()).decode(errors="replace").strip() or "daemon-reload ok")
    print(f"wrote {DROPIN} (keepalive 10 min; restart bridge after relogin ok)")
    ssh.close()


if __name__ == "__main__":
    main()
