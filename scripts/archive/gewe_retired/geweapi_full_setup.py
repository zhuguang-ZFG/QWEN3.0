#!/usr/bin/env python3
"""One-shot GeWeAPI setup: capture token (if needed) + VPS deploy + QR fetch to local HTML."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDS = ROOT / "data" / "geweapi_credentials.local.json"


def _has_token() -> bool:
    if CREDS.exists():
        return bool(json.loads(CREDS.read_text(encoding="utf-8")).get("token"))
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="")
    parser.add_argument("--paste", default="")
    args = parser.parse_args()

    token = args.token or args.paste
    if token:
        subprocess.check_call(
            [sys.executable, str(ROOT / "scripts/geweapi_capture_token.py"), "--paste", token],
        )
    elif not _has_token():
        print("=== 需要 GeWeAPI Token（仅一次）===")
        print("1. 浏览器打开 http://manager.geweapi.com 注册/登录（7 天试用）")
        print("2. Token 中心复制 TokenId，执行：")
        print("   python scripts/geweapi_full_setup.py --paste <TokenId>")
        rc = subprocess.call([sys.executable, str(ROOT / "scripts/geweapi_capture_token.py")])
        if rc != 0 or not _has_token():
            sys.exit(rc or 2)

    subprocess.check_call([sys.executable, str(ROOT / "scripts/deploy_geweapi_wechat.py")])
    subprocess.check_call(
        [
            sys.executable,
            str(ROOT / "scripts/wechat_joint_debug.py"),
            "refresh-qr",
            "--gewe-base",
            "https://www.geweapi.com/gewe/v2/api",
        ],
    )
    print("\n扫码: 打开 D:\\GIT\\data\\wechat_login_qr.html")
    print("或 HTTPS: https://chat.donglicao.com/gewe/login-qr")


if __name__ == "__main__":
    main()
