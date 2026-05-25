#!/usr/bin/env python3
"""VPS: align .env + invite cache to active iLink bot; archive stale account."""
import json
import os
import time
from pathlib import Path

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
ACCT_DIR = "/root/.hermes/weixin/accounts"


def run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _, o, e = ssh.exec_command(cmd, timeout=90)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)

    # Active account = newest non-context json by mtime
    pick = run(
        ssh,
        f"ls -t {ACCT_DIR}/*.json 2>/dev/null | grep -v context | grep -v sync | head -1",
    )
    if not pick:
        print("no account json")
        ssh.close()
        return

    raw = run(ssh, f"cat '{pick}'")
    data = json.loads(raw)
    account_id = Path(pick).name.replace(".json", "")
    token = data.get("token", "")
    base_url = data.get("base_url", "https://ilinkai.weixin.qq.com")

    print("active_account", account_id)

    # Archive old ffb299 account files
    run(
        ssh,
        f"mkdir -p {ACCT_DIR}/archive && "
        f"for f in {ACCT_DIR}/ffb299731947@im.bot*; do "
        f"[ -f \"$f\" ] && mv \"$f\" {ACCT_DIR}/archive/; done; "
        f"echo archived_ok",
    )

    # Write snippet + merge
    snippet = (
        f"WEIXIN_ACCOUNT_ID={account_id}\n"
        f"WEIXIN_TOKEN={token}\n"
        f"WEIXIN_BASE_URL={base_url}\n"
        "WEIXIN_DM_POLICY=open\n"
        "WEIXIN_GROUP_POLICY=disabled\n"
        "LIMA_CHANNEL_BASE_URL=http://127.0.0.1:8080\n"
        "LIMA_WEIXIN_AUTO_RELOGIN=1\n"
        "LIMA_WEIXIN_KEEPALIVE_MIN=10\n"
    )
    sftp = ssh.open_sftp()
    with sftp.file(f"{REMOTE}/data/weixin_ilink.env.snippet", "w") as f:
        f.write(snippet)
    with sftp.file(f"{REMOTE}/scripts/_merge_weixin_ilink_env_remote.py", "w") as f:
        f.write((Path(__file__).parent / "_merge_weixin_ilink_env_remote.py").read_text(encoding="utf-8"))
    sftp.close()

    print(run(ssh, f"cd {REMOTE} && python3.11 scripts/_merge_weixin_ilink_env_remote.py"))
    print(run(ssh, f"grep '^WEIXIN_ACCOUNT_ID=' {REMOTE}/.env"))

    # Refresh share QR with correct account_id (run weixin_share_qr on VPS)
    print(run(ssh, f"cd {REMOTE} && python3.11 scripts/weixin_share_qr.py 2>&1"))

    # Deploy fixed invite_qr if present locally - done in separate deploy step

    print(run(ssh, "systemctl restart lima-weixin-ilink && sleep 4 && systemctl is-active lima-weixin-ilink"))
    print(run(ssh, f"cat {REMOTE}/data/weixin_share_qr.json 2>/dev/null | head -20"))
    ssh.close()


if __name__ == "__main__":
    main()
