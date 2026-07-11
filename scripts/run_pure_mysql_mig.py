#!/usr/bin/env python3
from pathlib import Path
import time
import paramiko

HOST = "117.72.118.95"
LOCAL = Path(__file__).resolve().parents[1] / "deploy" / "jdcloud" / "pure_mysql_mig.py"
OUT = Path(r"D:\QWEN3.0\_mysql_mig_out.txt")


def password() -> str:
    for line in Path(r"D:\Downloads\VPS.txt").read_text(encoding="utf-8").splitlines():
        if HOST in line and "\u5bc6\u7801\uff1a" in line:
            return line.split("\u5bc6\u7801\uff1a", 1)[-1].strip()
    raise SystemExit("no pw")


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507  # one-off ops script, VPS host key unpinned
    c.connect(HOST, username="root", password=password(), timeout=25, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/pure_mysql_mig.py", "w") as f:
        f.write(LOCAL.read_text(encoding="utf-8"))
    sftp.close()

    chan = c.get_transport().open_session()
    chan.settimeout(30)
    chan.exec_command("python3 -u /tmp/pure_mysql_mig.py")
    buf = []
    deadline = time.time() + 420
    while True:
        if chan.recv_ready():
            chunk = chan.recv(4096).decode("utf-8", "replace")
            buf.append(chunk)
            print(chunk.encode("ascii", "replace").decode(), end="")
        if chan.recv_stderr_ready():
            chunk = chan.recv_stderr(4096).decode("utf-8", "replace")
            buf.append(chunk)
            print(chunk.encode("ascii", "replace").decode(), end="")
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        if time.time() > deadline:
            buf.append("\nTIMEOUT\n")
            break
        time.sleep(0.2)
    while chan.recv_ready():
        buf.append(chan.recv(4096).decode("utf-8", "replace"))
    code = chan.recv_exit_status() if chan.exit_status_ready() else 99
    text = "".join(buf)
    # redact
    safe = "\n".join("[redacted]" if ("PASS=" in l.upper() or "SQL_DSN=" in l) else l for l in text.splitlines())
    OUT.write_text(safe, encoding="utf-8")
    print("\nexit", code)
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
