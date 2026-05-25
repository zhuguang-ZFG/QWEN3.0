#!/usr/bin/env python3
"""GeWeAPI + LiMa sidecar full deploy: nginx HTTPS callback, env, QR, setCallback."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
NGINX_CONF = "/etc/nginx/conf.d/chat.donglicao.com.conf"
SNIPPET_MARK = "# LiMa WeChat sidecar (GeWeAPI webhook"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
CREDS_FILE = Path(__file__).resolve().parent.parent / "data" / "geweapi_credentials.local.json"

SIDEcar_FILES = [
    "wechat_bridge/__init__.py",
    "wechat_bridge/lima_client.py",
    "wechat_bridge/gewechat_client.py",
    "wechat_bridge/callback_handler.py",
    "wechat_bridge/sidecar_server.py",
]


def _load_token(args: argparse.Namespace) -> str:
    if args.token:
        return args.token.strip()
    env = os.environ.get("GEWECHAT_TOKEN", "").strip()
    if env:
        return env
    if CREDS_FILE.exists():
        data = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
        return str(data.get("token") or "").strip()
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="", help="GeWeAPI TokenId from manager console")
    parser.add_argument("--app-id", default="", help="Optional appId if already logged in console")
    parser.add_argument("--skip-nginx", action="store_true")
    parser.add_argument("--skip-qr", action="store_true")
    parser.add_argument("--infra-only", action="store_true", help="nginx + code upload only")
    args = parser.parse_args()

    token = _load_token(args)
    if not token and not args.infra_only:
        print("Missing GEWECHAT_TOKEN. Run: python scripts/geweapi_capture_token.py")
        sys.exit(2)

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    def run(cmd: str, timeout: int = 120) -> str:
        _i, o, e = ssh.exec_command(cmd, timeout=timeout)
        return (o.read() + e.read()).decode("utf-8", errors="replace")

    print("=== 1. Upload wechat_bridge ===")
    sftp = ssh.open_sftp()
    try:
        sftp.mkdir(f"{REMOTE}/wechat_bridge")
    except OSError:
        pass
    for rel in SIDEcar_FILES:
        sftp.put(str(base / rel), f"{REMOTE}/{rel}")
    for name in (
        "_patch_geweapi_env_remote.py",
        "_vps_refresh_qr_remote.py",
        "wechat_joint_debug.py",
    ):
        sftp.put(str(base / "scripts" / name), f"{REMOTE}/{name}")
    sftp.close()

    if not args.skip_nginx:
        print("=== 2. nginx HTTPS callback ===")
        sftp = ssh.open_sftp()
        sftp.put(
            str(base / "infra/vps/nginx/chat.donglicao.com.wechat-sidecar.snippet.conf"),
            f"{REMOTE}/chat.donglicao.com.wechat-sidecar.snippet.conf",
        )
        sftp.put(str(base / "scripts/_nginx_patch_wechat_remote.py"), f"{REMOTE}/_nginx_patch_wechat.py")
        sftp.close()
        print(run(f"/usr/local/bin/python3.10 {REMOTE}/_nginx_patch_wechat.py"))
        print(run("nginx -t && systemctl reload nginx"))

    if not args.infra_only:
        print("=== 3. Patch .env (GeWeAPI) ===")
        env = {"GEWECHAT_TOKEN": token}
        if args.app_id:
            env["GEWECHAT_APP_ID"] = args.app_id
        prefix = " ".join(f"{k}={v}" for k, v in env.items())
        print(run(f"{prefix} /usr/local/bin/python3.10 {REMOTE}/_patch_geweapi_env_remote.py"))
        print(run("systemctl restart lima-wechat-sidecar"))
        time.sleep(2)
        print(run("curl -sf http://127.0.0.1:9919/health"))

    if not args.skip_qr and not args.infra_only:
        print("=== 4. Login QR (API) ===")
        out = run(f"cd {REMOTE} && GEWECHAT_TOKEN={token} /usr/local/bin/python3.10 _vps_refresh_qr.py", timeout=300)
        print(out)
        if "qr_ok" not in out and not args.app_id:
            print("qr_failed_try_console_login")

    if not args.infra_only:
        print("=== 5. Public callback smoke ===")
        print(
            run(
                "curl -sf -o /dev/null -w '%{http_code}' -X POST "
                "https://chat.donglicao.com/gewe/v2/api/callback/collect "
                "-H 'Content-Type: application/json' -d '{\"TypeName\":\"ping\"}' || echo fail"
            )
        )

    ssh.close()
    if token:
        CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CREDS_FILE.write_text(
            json.dumps({"token": token, "app_id": args.app_id}, indent=2),
            encoding="utf-8",
        )
    print("\nDone.")
    print("QR local: file:///D:/GIT/data/wechat_login_qr.html")
    print("QR HTTPS: https://chat.donglicao.com/gewe/login-qr")
    print("After scan: python scripts/wechat_joint_debug.py poll-login")


if __name__ == "__main__":
    main()
