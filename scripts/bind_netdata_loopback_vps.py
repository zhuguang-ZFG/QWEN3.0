#!/usr/bin/env python3
"""Bind Netdata web UI/MCP to loopback only on VPS (PE-C-1 residual)."""

from __future__ import annotations

import os
import re
import sys

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
CONF_CANDIDATES = (
    "/opt/netdata/etc/netdata/netdata.conf",
    "/etc/netdata/netdata.conf",
)
BIND_VALUE = "127.0.0.1"
BIND_LINE = f"    bind to = {BIND_VALUE}"


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def _find_conf(ssh: paramiko.SSHClient) -> str:
    for path in CONF_CANDIDATES:
        code, _ = _run(ssh, f"test -f {path}")
        if code == 0:
            return path
    raise FileNotFoundError(f"netdata.conf not found in {CONF_CANDIDATES}")


def _ensure_loopback_bind(conf_text: str) -> tuple[str, bool]:
    """Return (new_text, changed)."""
    match = re.search(r"(?m)^(\s*)bind to\s*=\s*(.+)$", conf_text)
    if match:
        current = match.group(2).strip().lower()
        if current in (BIND_VALUE.lower(), "localhost", "127.0.0.1"):
            return conf_text, False
        new_text, n = re.subn(
            r"(?m)^(\s*)bind to\s*=.*$",
            rf"\1bind to = {BIND_VALUE}",
            conf_text,
            count=1,
        )
        return new_text, n > 0

    match = re.search(r"(?m)^\[web\]\s*$", conf_text)
    if match:
        insert_at = match.end()
        new_text = conf_text[:insert_at] + f"\n{BIND_LINE}" + conf_text[insert_at:]
        return new_text, True

    new_text = conf_text.rstrip() + f"\n\n[web]\n{BIND_LINE}\n"
    return new_text, True


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    conf_path = _find_conf(ssh)
    before_listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 19999 || true")[1]
    _, conf_text = _run(ssh, f"cat {conf_path}")
    new_text, changed = _ensure_loopback_bind(conf_text)

    if not changed:
        print(f"netdata_conf={conf_path} bind_already_loopback=1")
    else:
        backup = f"{conf_path}.bak.loopback"
        _run(ssh, f"cp {conf_path} {backup}")
        sftp = ssh.open_sftp()
        with sftp.file(conf_path, "w") as remote:
            remote.write(new_text)
        sftp.close()
        code, out = _run(
            ssh,
            "systemctl restart netdata && sleep 2 && systemctl is-active netdata",
            timeout=180,
        )
        if code != 0 or "active" not in out:
            print(f"restart_failed code={code} out={out[:200]}")
            ssh.close()
            return 1
        print(f"netdata_conf={conf_path} backup={backup} restarted=1")

    after_listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 19999 || true")[1]
    info_code, _ = _run(ssh, "curl -sf http://127.0.0.1:19999/api/v1/info", timeout=20)
    ssh.close()

    print(f"listen_before={before_listen.replace(chr(10), ' ')[:120]}")
    print(f"listen_after={after_listen.replace(chr(10), ' ')[:120]}")
    loopback_ok = "127.0.0.1:19999" in after_listen and "0.0.0.0:19999" not in after_listen
    print(f"loopback_ok={loopback_ok} api_ok={info_code == 0}")
    print("bind_loopback_ok" if loopback_ok and info_code == 0 else "bind_loopback_FAILED")
    return 0 if loopback_ok and info_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
