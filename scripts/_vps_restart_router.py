#!/usr/bin/env python3
import os
import paramiko
from deploy_common import configure_ssh_host_keys

KEY = os.path.expanduser("~/.ssh/id_ed25519")


def main() -> None:
    ssh = paramiko.SSHClient()
    configure_ssh_host_keys(ssh)
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    for cmd in [
        "systemctl restart lima-router && sleep 4 && systemctl is-active lima-router",
        "journalctl -u lima-weixin-ilink -n 12 --no-pager",
    ]:
        _, o, e = ssh.exec_command(cmd, timeout=60)
        print((o.read() + e.read()).decode(errors="replace"))
    ssh.close()


if __name__ == "__main__":
    main()
