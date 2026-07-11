#!/usr/bin/env python3
"""Deploy newapi_backup.sh to JDCloud and install daily cron. No secrets printed."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("LIMA_JDCLOUD_SERVER", "117.72.118.95")
REPO = Path(__file__).resolve().parents[1]
LOCAL = REPO / "deploy" / "jdcloud" / "newapi_backup.sh"


def password() -> str:
    pw = (os.environ.get("LIMA_JDCLOUD_SSH_PASS") or os.environ.get("JDCLOUD_SSH_PASSWORD") or "").strip()
    if pw:
        return pw
    vps = Path(r"D:\Downloads\VPS.txt")
    if vps.is_file():
        for line in vps.read_text(encoding="utf-8", errors="replace").splitlines():
            if HOST in line and "\u5bc6\u7801" in line:  # 密码
                # formats: "密码：xxx" or "密码:xxx"
                for sep in ("\u5bc6\u7801\uff1a", "\u5bc6\u7801:"):
                    if sep in line:
                        return line.split(sep, 1)[-1].strip()
    raise SystemExit("set LIMA_JDCLOUD_SSH_PASS or put password in D:\\Downloads\\VPS.txt")


def main() -> int:
    if not LOCAL.is_file():
        raise SystemExit(f"missing {LOCAL}")
    script = LOCAL.read_text(encoding="utf-8")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507  # one-off ops script, VPS host key unpinned
    client.connect(HOST, username="root", password=password(), timeout=25, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    with sftp.file("/opt/newapi/backup.sh", "w") as f:
        f.write(script)
    sftp.close()

    cmd = r"""
set -e
chmod +x /opt/newapi/backup.sh
if ! command -v sqlite3 >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sqlite3 >/dev/null
fi
CRON_LINE='13 3 * * * /opt/newapi/backup.sh >> /var/log/newapi-backup.log 2>&1'
(crontab -l 2>/dev/null | grep -v '/opt/newapi/backup.sh' || true; echo "$CRON_LINE") | crontab -
echo '--- crontab ---'
crontab -l | grep backup || true
echo '--- trial run ---'
/opt/newapi/backup.sh
echo '--- latest ---'
ls -lht /var/backups/newapi | head -5
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=180)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    print(out)
    if err.strip():
        print(err[:800], file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
