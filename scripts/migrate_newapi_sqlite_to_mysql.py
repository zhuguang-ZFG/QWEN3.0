#!/usr/bin/env python3
"""Run migrate_newapi_sqlite_to_mysql.sh on JDCloud; write log locally."""

from __future__ import annotations

from pathlib import Path

import paramiko

HOST = "117.72.118.95"
REPO = Path(__file__).resolve().parents[1]
LOCAL = REPO / "deploy" / "jdcloud" / "migrate_newapi_sqlite_to_mysql.sh"
OUT = REPO / "_mysql_mig_out.txt"


def password() -> str:
    for line in Path(r"D:\Downloads\VPS.txt").read_text(encoding="utf-8").splitlines():
        if HOST in line and "\u5bc6\u7801\uff1a" in line:
            return line.split("\u5bc6\u7801\uff1a", 1)[-1].strip()
    raise SystemExit("no pw")


def main() -> int:
    script = LOCAL.read_text(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507  # one-off ops script, VPS host key unpinned
    c.connect(HOST, username="root", password=password(), timeout=25, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/migrate_newapi_sqlite_to_mysql.sh", "w") as f:
        f.write(script)
    sftp.close()
    # Pre-install tool FIRST while service still up (reduces downtime)
    pre = r"""
set -e
VENV=/opt/newapi/.venv-mig
IDX=https://pypi.tuna.tsinghua.edu.cn/simple
if [ ! -x "$VENV/bin/sqlite3mysql" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -U pip -i "$IDX" --timeout 30
  timeout 90 "$VENV/bin/pip" install -q sqlite3-to-mysql -i "$IDX" --timeout 30
fi
"$VENV/bin/sqlite3mysql" --help >/dev/null
echo PREINSTALL_OK
"""
    _, o, e = c.exec_command(pre, timeout=150)
    pre_out = o.read().decode("utf-8", "replace")
    pre_err = e.read().decode("utf-8", "replace")
    pre_code = o.channel.recv_exit_status()
    if pre_code != 0 or "PREINSTALL_OK" not in pre_out:
        OUT.write_text(pre_out + "\n" + pre_err, encoding="utf-8")
        print(pre_out)
        print(pre_err[:800])
        c.close()
        return pre_code or 1
    print("preinstall OK")

    _, o, e = c.exec_command(
        "bash /tmp/migrate_newapi_sqlite_to_mysql.sh",
        timeout=300,
    )
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    c.close()
    # redact
    safe = []
    for line in (out + "\n" + err).splitlines():
        if "PASS=" in line.upper() or "SQL_DSN=" in line or "password" in line.lower():
            safe.append("[redacted]")
        else:
            safe.append(line)
    text = "\n".join(safe)
    OUT.write_text(text, encoding="utf-8")
    print(text[-3000:] if len(text) > 3000 else text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
