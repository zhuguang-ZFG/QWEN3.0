#!/usr/bin/env python3
"""Remove retired WeChat/iLink artifacts from LiMa VPS (wechat_bridge tree, units, data)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

# Keep LIMA_WECHAT_SIDECAR_TOKEN for /channel contract smoke; drop iLink-only knobs.
ENV_KEYS_DROP = (
    "LIMA_WEIXIN_AUTO_RELOGIN",
    "LIMA_WEIXIN_KEEPALIVE_MIN",
    "LIMA_WEIXIN_BOT_ID",
    "WEIXIN_ACCOUNT_ID",
    "LIMA_WECHAT_PUBLIC_ID",
)

REMOTE_PATHS = (
    f"{REMOTE}/wechat_bridge",
    f"{REMOTE}/scripts/hermes_weixin_lima_bridge.py",
    f"{REMOTE}/scripts/hermes_weixin_qr_login.py",
    f"{REMOTE}/scripts/weixin_share_qr.py",
    f"{REMOTE}/scripts/_merge_weixin_ilink_env_remote.py",
    f"{REMOTE}/scripts/_merge_weixin_ilink_env.py",
    f"{REMOTE}/scripts/_vps_deploy_invite_fix.py",
    f"{REMOTE}/scripts/_vps_fake_wechat_smoke_remote.py",
    f"{REMOTE}/scripts/wechat_fake_vps_smoke.py",
    f"{REMOTE}/scripts/wechat_bridge_fake.py",
    f"{REMOTE}/scripts/check_weixin_deploy.py",
    f"{REMOTE}/requirements-weixin-ilink.txt",
    f"{REMOTE}/requirements-wcf.txt",
    f"{REMOTE}/data/weixin_share_qr.json",
    f"{REMOTE}/data/weixin_share_qr.html",
    f"{REMOTE}/data/weixin_ilink.env.snippet",
    f"{REMOTE}/data/weixin_relogin_qr.html",
    f"{REMOTE}/data/hermes_weixin_login_qr.html",
    f"{REMOTE}/data/hermes_weixin_login_status.json",
    f"{REMOTE}/data/weixin_relogin_status.json",
    f"{REMOTE}/_nginx_patch_wechat.py",
    f"{REMOTE}/_vps_fake_wechat_smoke.py",
    f"{REMOTE}/tests/test_wechat_channel_smoke.py",
    f"{REMOTE}/scripts/smoke_wechat_channel_gateway.py",
    "/etc/systemd/system/lima-weixin-ilink.service",
    "/etc/systemd/system/lima-wechat-sidecar.service",
)


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def _strip_env(ssh: paramiko.SSHClient) -> None:
    drop = set(ENV_KEYS_DROP)
    py = f'''
from pathlib import Path
p = Path("{REMOTE}/.env")
if not p.exists():
    print("env_missing")
    raise SystemExit(0)
lines = p.read_text(encoding="utf-8").splitlines()
out = []
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in {repr(drop)}:
            continue
    out.append(line)
# ensure bridge off
data = {{}}
for line in out:
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
data["WECHAT_BRIDGE_ENABLED"] = "0"
seen = set()
final = []
for line in out:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in data:
            final.append(f"{{k}}={{data[k]}}")
            seen.add(k)
        else:
            final.append(line)
    else:
        final.append(line)
if "WECHAT_BRIDGE_ENABLED" not in seen:
    final.append("WECHAT_BRIDGE_ENABLED=0")
p.write_text("\\n".join(final) + "\\n", encoding="utf-8")
print("env_wechat_ilink_stripped")
'''
    sftp = ssh.open_sftp()
    sftp.file(f"{REMOTE}/_strip_wechat_env.py", "w").write(py.encode("utf-8"))
    sftp.close()
    print(_run(ssh, f"cd {REMOTE} && python3.10 _strip_wechat_env.py && rm -f _strip_wechat_env.py"))


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not os.path.isfile(KEY):
        print(f"SSH key missing: {KEY}")
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    print("=== before (wechat-related paths) ===")
    print(
        _run(
            ssh,
            f"find {REMOTE} -maxdepth 3 \\( -path '*wechat*' -o -path '*weixin*' -o -path '*hermes_weixin*' \\) "
            "2>/dev/null | head -40 || true",
        )
    )

    steps = [
        ("stop ilink", "systemctl stop lima-weixin-ilink 2>/dev/null || true"),
        ("disable ilink", "systemctl disable lima-weixin-ilink 2>/dev/null || true"),
        ("stop sidecar", "systemctl stop lima-wechat-sidecar 2>/dev/null || true"),
        ("disable sidecar", "systemctl disable lima-wechat-sidecar 2>/dev/null || true"),
        ("remove units", "rm -f /etc/systemd/system/lima-weixin-ilink.service "
         "/etc/systemd/system/lima-wechat-sidecar.service"),
        ("remove dropins", "rm -rf /etc/systemd/system/lima-weixin-ilink.service.d"),
        ("daemon-reload", "systemctl daemon-reload"),
    ]

    if dry:
        for name, cmd in steps:
            print(f"[dry] {name}: {cmd}")
        for path in REMOTE_PATHS:
            print(f"[dry] rm -rf {path}")
        ssh.close()
        return 0

    for name, cmd in steps:
        print(f"=== {name} ===")
        print(_run(ssh, cmd))

    print("=== remove paths ===")
    for path in REMOTE_PATHS:
        out = _run(ssh, f"rm -rf {path} 2>/dev/null; test -e {path} && echo STILL_EXISTS:{path} || echo removed:{path}")
        if out:
            print(out)

    _strip_env(ssh)

    print("=== after ===")
    print(
        _run(
            ssh,
            f"find {REMOTE} -maxdepth 3 \\( -path '*wechat*' -o -path '*weixin*' \\) 2>/dev/null | head -20 || echo none",
        )
    )
    print(_run(ssh, "grep '^WECHAT_BRIDGE_ENABLED=' /opt/lima-router/.env || true"))
    print(_run(ssh, "systemctl is-active lima-weixin-ilink 2>&1 || echo ilink_inactive"))
    print(_run(ssh, "systemctl is-active lima-router"))
    print(_run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 120"))

    ssh.close()
    print("cleanup_wechat_vps done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
