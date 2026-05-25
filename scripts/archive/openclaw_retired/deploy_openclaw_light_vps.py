#!/usr/bin/env python3
"""Lightweight OpenClaw on LiMa VPS: WeChat plugin only, LiMa API brain.

Does NOT stop lima-weixin-ilink (parallel validation). Gateway binds loopback:18789.
"""

from __future__ import annotations

import os
import secrets
import sys
import time
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SERVICE = "lima-openclaw"
OPENCLAW_VER = os.environ.get("OPENCLAW_VERSION", "2026.5.22")
OC_HOME = f"{REMOTE}/openclaw"
OC_STATE = f"{OC_HOME}/state"
OC_CFG = f"{OC_HOME}/openclaw.json"


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = 180) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return (out + ("\n" + err if err.strip() else "")).strip()


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"SSH key not found: {KEY}", file=sys.stderr)
        return 1

    base = Path(__file__).resolve().parent.parent
    cfg_src = base / "deploy" / "openclaw" / "openclaw.light.json5"
    unit_src = base / "deploy" / "openclaw" / "lima-openclaw.service"
    if not cfg_src.is_file() or not unit_src.is_file():
        print("missing deploy/openclaw assets", file=sys.stderr)
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    print("=== 1. Node.js 22 (OpenClaw runtime) ===")
    print(
        _run(
            ssh,
            "command -v node >/dev/null 2>&1 && node --version || "
            "(curl -fsSL https://rpm.nodesource.com/setup_22.x | bash - && "
            "dnf install -y nodejs 2>/dev/null || yum install -y nodejs) && node --version",
            timeout=300,
        )
    )

    NVM_NODE = "/root/.nvm/versions/node/v22.22.1/bin"
    npm_g = f"export PATH={NVM_NODE}:$PATH; npm install -g openclaw@{OPENCLAW_VER}"
    print("=== 2. OpenClaw CLI + WeChat plugin ===")
    print(_run(ssh, npm_g, timeout=300))
    print(_run(ssh, f"export PATH={NVM_NODE}:$PATH; openclaw --version"))
    env_oc = (
        f"export PATH={NVM_NODE}:$PATH OPENCLAW_STATE_DIR={OC_STATE} "
        f"OPENCLAW_CONFIG_PATH={OC_CFG} HOME=/root; "
    )
    _run(ssh, f"mkdir -p {OC_HOME}/workspace {OC_STATE}/extensions")
    print(
        _run(
            ssh,
            f"{env_oc} openclaw plugins install @tencent-weixin/openclaw-weixin --pin",
            timeout=300,
        )
    )

    print("=== 3. Config + workspace ===")
    sftp = ssh.open_sftp()
    _run(ssh, f"mkdir -p {OC_HOME}")
    sftp.put(str(cfg_src), OC_CFG)
    for sh_name in ("openclaw_gateway_start.sh", "openclaw_weixin_login_vps.sh"):
        sh = base / "scripts" / sh_name
        sftp.put(str(sh), f"{REMOTE}/scripts/{sh_name}")
        _run(ssh, f"chmod +x {REMOTE}/scripts/{sh_name}")
    sftp.close()

    print("=== 4. Merge .env (LIMA_API_KEY, OPENCLAW_GATEWAY_TOKEN) ===")
    merge_py = r"""
import secrets
from pathlib import Path
p = Path("/opt/lima-router/.env")
lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
kv = {}
for ln in lines:
    s = ln.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    kv[k.strip()] = v.strip()
changed = False
if not kv.get("LIMA_API_KEY"):
    print("WARN: LIMA_API_KEY missing in .env — set before WeChat chat works")
if not kv.get("OPENCLAW_GATEWAY_TOKEN"):
    kv["OPENCLAW_GATEWAY_TOKEN"] = secrets.token_urlsafe(32)
    changed = True
    print("ADD OPENCLAW_GATEWAY_TOKEN")
out = []
seen = set()
for ln in lines:
    s = ln.strip()
    if s and not s.startswith("#") and "=" in s:
        k = s.split("=", 1)[0].strip()
        if k in kv:
            out.append(f"{k}={kv[k]}")
            seen.add(k)
            continue
    out.append(ln)
for k, v in kv.items():
    if k not in seen:
        out.append(f"{k}={v}")
if changed or len(out) != len(lines):
    p.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
print("env_ok keys=", ",".join(sorted(kv.keys())))
"""
    sftp = ssh.open_sftp()
    remote_merge = f"{REMOTE}/scripts/_openclaw_merge_env.py"
    sftp.putfo(__import__("io").BytesIO(merge_py.encode()), remote_merge)
    sftp.close()
    print(_run(ssh, f"mkdir -p {REMOTE}/scripts && {REMOTE}/bin/python3.10 {remote_merge} 2>/dev/null || python3.10 {remote_merge} || python3.11 {remote_merge}"))

    unit = unit_src.read_text(encoding="utf-8")
    sftp = ssh.open_sftp()
    with sftp.file(f"/etc/systemd/system/{SERVICE}.service", "w") as fh:
        fh.write(unit)
    sftp.close()

    print("=== 5. systemd (parallel with lima-weixin-ilink) ===")
    print(_run(ssh, "systemctl daemon-reload && systemctl enable " + SERVICE))
    print(_run(ssh, "systemctl restart " + SERVICE))
    time.sleep(5)
    print(_run(ssh, "systemctl is-active " + SERVICE))
    print(_run(ssh, f"journalctl -u {SERVICE} -n 25 --no-pager"))

    print("=== 6. Lint / health ===")
    print(
        _run(
            ssh,
            f"bash -lc 'set -a && source {REMOTE}/.env && set +a && "
            f"unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET && "
            f"{env_oc} openclaw doctor --lint 2>&1'",
            timeout=120,
        )
    )
    print(_run(ssh, "curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/ 2>/dev/null || echo no_http"))
    print(_run(ssh, f"{env_oc} openclaw channels list 2>&1", timeout=60))

    print("\n=== Next (manual) ===")
    print("SSH to VPS, run WeChat login (prints QR URL):")
    print(f"  export OPENCLAW_STATE_DIR={OC_STATE} OPENCLAW_CONFIG_PATH={OC_CFG}")
    print("  openclaw channels login --channel openclaw-weixin")
    print("Friend scan -> openclaw pairing list openclaw-weixin -> pairing approve ...")
    print("Keep lima-weixin-ilink running until OpenClaw validated; do not share iLink token.")

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
