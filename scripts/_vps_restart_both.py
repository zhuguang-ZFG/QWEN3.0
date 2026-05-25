#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    for cmd in [
        "systemctl restart lima-router lima-weixin-ilink && sleep 5",
        "systemctl is-active lima-router lima-weixin-ilink",
        "cd /opt/lima-router && python3.10 scripts/_vps_fake_wechat_smoke_remote.py",
    ]:
        _, o, e = ssh.exec_command(cmd, timeout=90)
        print((o.read() + e.read()).decode(errors="replace"))
    ssh.close()


if __name__ == "__main__":
    main()
