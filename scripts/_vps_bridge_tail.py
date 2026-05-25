#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    cmds = [
        "journalctl -u lima-weixin-ilink --since '20:06:00' --no-pager | tail -80",
        "grep WEIXIN_ACCOUNT /opt/lima-router/.env | head -3",
        "python3.11 -c \"import json;from pathlib import Path;p=Path('/opt/lima-router/data/weixin_share_qr.json');print(p.read_text()[:400] if p.exists() else 'no share json')\"",
    ]
    for c in cmds:
        print("\n>>>", c[:70])
        _, o, e = ssh.exec_command(c, timeout=60)
        print((o.read() + e.read()).decode(errors="replace"))
    ssh.close()


if __name__ == "__main__":
    main()
