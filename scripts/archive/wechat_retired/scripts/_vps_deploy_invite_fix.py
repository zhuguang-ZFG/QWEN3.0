#!/usr/bin/env python3
"""Upload invite fix files and run VPS account alignment."""
import os
from pathlib import Path

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
BASE = Path(__file__).resolve().parent.parent

FILES = [
    ("wechat_bridge/invite_qr.py", f"{REMOTE}/wechat_bridge/invite_qr.py"),
    ("wechat_bridge/weixin_outbound.py", f"{REMOTE}/wechat_bridge/weixin_outbound.py"),
    ("channel_gateway/invite.py", f"{REMOTE}/channel_gateway/invite.py"),
    ("channel_gateway/service.py", f"{REMOTE}/channel_gateway/service.py"),
    ("scripts/_merge_weixin_ilink_env_remote.py", f"{REMOTE}/scripts/_merge_weixin_ilink_env_remote.py"),
    ("scripts/_vps_fake_wechat_smoke_remote.py", f"{REMOTE}/scripts/_vps_fake_wechat_smoke_remote.py"),
    ("scripts/weixin_share_qr.py", f"{REMOTE}/scripts/weixin_share_qr.py"),
]


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    sftp = ssh.open_sftp()
    for rel, remote in FILES:
        local = BASE / rel.replace("/", os.sep)
        sftp.put(str(local), remote)
        print("uploaded", rel)
    sftp.close()
    ssh.close()
    print("done uploads; run _vps_fix_invite_account.py next")


if __name__ == "__main__":
    main()
