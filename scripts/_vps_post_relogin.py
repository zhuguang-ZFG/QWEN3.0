#!/usr/bin/env python3
"""Post-relogin: restart for keepalive=10, list accounts, tail logs."""
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"


def run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _, o, e = ssh.exec_command(cmd, timeout=60)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)

    print("=== accounts ===")
    print(run(ssh, "ls -la /root/.hermes/weixin/accounts/*.json 2>/dev/null | grep -v context | grep -v sync"))

    print("\n=== active account in bridge log ===")
    print(
        run(
            ssh,
            "journalctl -u lima-weixin-ilink --since '2 min ago' --no-pager 2>/dev/null | "
            "grep -E 'bridge account=|relogin OK|errcode=-14|credentials reloaded|keepalive' | tail -8",
        )
    )

    print("\n=== restart for keepalive=10 ===")
    print(run(ssh, "systemctl restart lima-weixin-ilink && sleep 4 && systemctl is-active lima-weixin-ilink"))

    print("\n=== after restart (10s) ===")
    import time

    time.sleep(6)
    print(
        run(
            ssh,
            "journalctl -u lima-weixin-ilink --since '30 sec ago' --no-pager 2>/dev/null | "
            "grep -E 'bridge account=|keepalive|errcode=-14|relogin OK|session dead' | tail -10",
        )
    )
    ssh.close()


if __name__ == "__main__":
    main()
