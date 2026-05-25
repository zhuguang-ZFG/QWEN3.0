#!/usr/bin/env python3
"""Print iLink relogin QR URL and bridge status from VPS."""
import json
import os
from pathlib import Path

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"


def run(cmd: str) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    _, o, e = ssh.exec_command(cmd, timeout=60)
    out = (o.read() + e.read()).decode(errors="replace")
    ssh.close()
    return out.strip()


def main() -> None:
    print("=== systemd ===")
    print(run("systemctl is-active lima-weixin-ilink"))
    print("\n=== last logs ===")
    print(run("journalctl -u lima-weixin-ilink -n 15 --no-pager 2>/dev/null | tail -15"))
    print("\n=== relogin status ===")
    print(run("cat /opt/lima-router/data/weixin_relogin_status.json 2>/dev/null || echo none"))
    print("\n=== relogin html (link) ===")
    html = run("grep -o 'https://liteapp[^\"<]*' /opt/lima-router/data/weixin_relogin_qr.html 2>/dev/null | head -1")
    print(html or "no link in html")
    print("\n=== account token present ===")
    print(run("python3.11 -c \"import json;from pathlib import Path;p=list(Path('/root/.hermes/weixin/accounts').glob('*.json'));p=[x for x in p if 'context' not in x.name];d=json.loads(p[0].read_text()) if p else {};print(p[0].stem if p else 'none', 'token_len', len(d.get('token','')))\""))


if __name__ == "__main__":
    main()
