#!/usr/bin/env python3
"""Deploy newapi_healthcheck.sh to JDCloud and install */5 cron. No Claude chat."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

from scripts.deploy_common import configure_ssh_host_keys

HOST = os.environ.get("LIMA_JDCLOUD_SERVER", "117.72.118.95")
REPO = Path(__file__).resolve().parents[1]
LOCAL = REPO / "deploy" / "jdcloud" / "newapi_healthcheck.sh"


def password() -> str:
    pw = (os.environ.get("LIMA_JDCLOUD_SSH_PASS") or os.environ.get("JDCLOUD_SSH_PASSWORD") or "").strip()
    if pw:
        return pw
    vps = Path(r"D:\Downloads\VPS.txt")
    if vps.is_file():
        for line in vps.read_text(encoding="utf-8", errors="replace").splitlines():
            if HOST in line and "\u5bc6\u7801" in line:
                for sep in ("\u5bc6\u7801\uff1a", "\u5bc6\u7801:"):
                    if sep in line:
                        return line.split(sep, 1)[-1].strip()
    raise SystemExit("set LIMA_JDCLOUD_SSH_PASS or put password in D:\\Downloads\\VPS.txt")


def _uuid_cmd() -> str:
    uuid = (os.environ.get("NEWAPI_HC_PING_UUID") or "").strip()
    if not uuid:
        return ""
    return f"""
grep -q '^NEWAPI_HC_PING_UUID=' /opt/newapi/.env.backup 2>/dev/null \\
  && sed -i 's/^NEWAPI_HC_PING_UUID=.*/NEWAPI_HC_PING_UUID={uuid}/' /opt/newapi/.env.backup \\
  || echo 'NEWAPI_HC_PING_UUID={uuid}' >> /opt/newapi/.env.backup
chmod 600 /opt/newapi/.env.backup 2>/dev/null || true
"""


def _install_remote_cmd() -> str:
    return f"""
set -e
chmod +x /opt/newapi/healthcheck.sh
touch /opt/newapi/.env.backup
chmod 600 /opt/newapi/.env.backup
{_uuid_cmd()}
CRON_LINE='*/5 * * * * /opt/newapi/healthcheck.sh >> /var/log/newapi-healthcheck.log 2>&1'
(crontab -l 2>/dev/null | grep -v '/opt/newapi/healthcheck.sh' || true; echo "$CRON_LINE") | crontab -
echo '--- crontab ---'
crontab -l | grep -E 'newapi/(backup|healthcheck)' || true
echo '--- trial run ---'
/opt/newapi/healthcheck.sh; echo exit=$?
echo '--- log tail ---'
tail -3 /var/log/newapi-healthcheck.log 2>/dev/null || true
if grep -q '^NEWAPI_HC_PING_UUID=.' /opt/newapi/.env.backup 2>/dev/null; then
  echo 'HC_PING=configured'
else
  echo 'HC_PING=skipped (set NEWAPI_HC_PING_UUID to enable healthchecks.io)'
fi
"""


def main() -> int:
    if not LOCAL.is_file():
        raise SystemExit(f"missing {LOCAL}")
    script = LOCAL.read_text(encoding="utf-8")
    client = paramiko.SSHClient()
    configure_ssh_host_keys(client)
    client.connect(HOST, username="root", password=password(), timeout=25, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    with sftp.file("/opt/newapi/healthcheck.sh", "w") as f:
        f.write(script)
    sftp.close()

    _, stdout, stderr = client.exec_command(_install_remote_cmd(), timeout=90)
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
