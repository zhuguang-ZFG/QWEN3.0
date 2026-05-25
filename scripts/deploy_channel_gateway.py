#!/usr/bin/env python3
"""Deploy WeChat channel gateway (CQ-088/089/090) to LiMa VPS."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "mimo_stt.py",
    "mimo_tts.py",
    "routes/channel_gateway.py",
    "routes/route_registry.py",
    "search_gateway/__init__.py",
    "search_gateway/safety.py",
    "search_gateway/policy.py",
    "search_gateway/dev_tools.py",
    "search_gateway/anysearch_adapter.py",
    "search_gateway/tinyfish_transport.py",
]

CHANNEL_GATEWAY_FILES = [
    "__init__.py",
    "models.py",
    "store.py",
    "commands.py",
    "service.py",
    "integrations.py",
    "channel_tools.py",
    "public_apis.py",
    "tool_usage.py",
    "chat_session.py",
    "branding.py",
    "media_inbound.py",
    "keyword_router.py",
    "invite.py",
    "nl_tool_router.py",
    "voice_reply.py",
    "outbound_pack.py",
]

ENV_FLAGS = {
    "WECHAT_BRIDGE_ENABLED": "1",
    "LIMA_CHANNEL_TOOLS": "1",
    "LIMA_CHANNEL_SESSION": "1",
    "LIMA_CHANNEL_AUTO_GUEST_BIND": "1",
    "LIMA_CHANNEL_DB_PATH": "data/channel_gateway.db",
    "LIMA_CHANNEL_VOICE_REPLY": "1",
    "LIMA_CHANNEL_INVITE_QR": "1",
}

def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
    try:
        out = stdout.read().decode("utf-8", errors="replace")
    except Exception:
        out = ""
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _restart_router(ssh: paramiko.SSHClient) -> None:
    _run(ssh, "systemctl stop lima-router 2>/dev/null || true")
    _run(ssh, "pkill -9 -f 'uvicorn server:app' || true")
    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(3)
    _run(ssh, "systemctl reset-failed lima-router 2>/dev/null || true")
    _run(ssh, "systemctl enable lima-router 2>/dev/null || true")
    out = _run(ssh, "systemctl start lima-router 2>&1", timeout=15)
    if out:
        _log(out[:200])
    time.sleep(6)
    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    if active != "active":
        _log("lima-router not active: " + _run(ssh, "journalctl -u lima-router -n 8 --no-pager"))


def main() -> None:
    run_smoke = "--smoke" in sys.argv
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("no VPS backup (rollback via GitHub)")

    sftp = ssh.open_sftp()
    try:
        sftp.mkdir(f"{REMOTE}/channel_gateway")
    except OSError:
        pass
    try:
        sftp.mkdir(f"{REMOTE}/data")
    except OSError:
        pass

    for name in CHANNEL_GATEWAY_FILES:
        local = base / "channel_gateway" / name
        remote = f"{REMOTE}/channel_gateway/{name}"
        sftp.put(str(local), remote)
        _log(f"uploaded channel_gateway/{name}")

    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass
        sftp.put(str(local), remote)
        _log(f"uploaded {rel}")

    share_json = base / "data" / "weixin_share_qr.json"
    if share_json.is_file():
        sftp.put(str(share_json), f"{REMOTE}/data/weixin_share_qr.json")
        _log("uploaded data/weixin_share_qr.json")
    sftp.close()

    _run(ssh, f"mkdir -p {REMOTE}/data")
    patch_local = base / "scripts" / "_patch_channel_env_remote.py"
    sftp = ssh.open_sftp()
    sftp.put(str(patch_local), f"{REMOTE}/_patch_channel_env.py")
    sftp.close()
    patch_out = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 _patch_channel_env.py",
        timeout=30,
    )
    _log(patch_out)

    _restart_router(ssh)

    port = _run(ssh, "ss -tlnp | grep 8080 || true")
    if "8080" not in port:
        _log("FAILED: port 8080 not listening")
        _log(_run(ssh, "tail -40 /var/log/lima-server.log"))
        ssh.close()
        sys.exit(1)

    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 120")
    _log(f"health: {health}")
    ssh.close()

    if run_smoke:
        import subprocess

        smoke = Path(__file__).resolve().parent / "vps_run_channel_smoke.py"
        subprocess.run([sys.executable, str(smoke)], check=True)
        _log("smoke_token channel_gateway_vps_ok")


if __name__ == "__main__":
    main()
