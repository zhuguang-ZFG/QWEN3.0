#!/usr/bin/env python3
"""Fetch device-app JWT on VPS and run voice E2E probes against production.

Strict mode (LIMA_VOICE_E2E_STRICT=1) uses scripts/fixtures/voice_probe_draw_cat.wav
and expects transcript containing 画/猫 plus draw_generated intent.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from deploy_unified_common import get_deploy_target
from deploy_unified_restart import _connect_ssh, _ssh_exec
from voice_e2e_probe import exit_code_for_results, print_probe_results, run_voice_e2e_probes

REMOTE_LOGIN = r"""python3 - <<'PY'
import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out

env = load_env(Path("/opt/dlc-drawing/.env"))
base = "http://127.0.0.1:8081"

def post_login(code: str) -> dict | None:
    req = urllib.request.Request(
        f"{base}/device/v1/app/auth/login",
        data=json.dumps({"code": code}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(json.dumps({"error": f"login_http_{exc.code}", "body": exc.read().decode()[:200]}))
        return None

body = post_login("e2e-voice-probe")
if body and body.get("token"):
    print(json.dumps({"token": body["token"], "accountId": body.get("accountId"), "source": "wechat_dev_login"}))
    raise SystemExit(0)

secret = env.get("LIMA_JWT_SECRET", "")
db_path = env.get("LIMA_DB_PATH", "/opt/dlc-drawing/data/lima.db")
if not secret:
    print(json.dumps({"error": "no_jwt_secret_and_login_failed"}))
    raise SystemExit(1)

try:
    import jwt
except ImportError:
    print(json.dumps({"error": "pyjwt_missing_on_server"}))
    raise SystemExit(1)

conn = sqlite3.connect(db_path)
row = conn.execute("SELECT id FROM v2_account WHERE status='active' LIMIT 1").fetchone()
conn.close()
if not row:
    print(json.dumps({"error": "no_active_account"}))
    raise SystemExit(1)

account_id = row[0]
now = int(time.time())
token = jwt.encode(
    {"sub": account_id, "account_id": account_id, "role": "user", "iat": now, "exp": now + 3600},
    secret,
    algorithm="HS256",
)
print(json.dumps({"token": token, "accountId": account_id, "source": "minted_jwt"}))
PY"""


def main() -> int:
    target = get_deploy_target()
    ssh = _connect_ssh(target)
    try:
        code, out, err = _ssh_exec(ssh, REMOTE_LOGIN)
    finally:
        ssh.close()

    if err:
        print(f"remote stderr: {err[:400]}")
    if code != 0 and not out:
        print(f"remote login failed (exit {code})")
        return 1

    try:
        payload = json.loads(out.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        print(f"unexpected remote output: {out[:400]}")
        return 1

    if payload.get("error"):
        print(f"token error: {payload['error']}")
        return 1

    token = str(payload.get("token") or "")
    if not token:
        print(f"missing token in payload: {payload}")
        return 1

    source = payload.get("source", "?")
    account = payload.get("accountId", "?")
    print(f"token acquired via {source} accountId={account}")

    host = os.environ.get("LIMA_VERIFY_HOST", "chat.donglicao.com")
    strict = os.environ.get("LIMA_VOICE_E2E_STRICT", "").strip().lower() in {"1", "true", "yes"}
    print(f"Voice E2E host: https://{host} strict={strict}")

    results = asyncio.run(run_voice_e2e_probes(host, token=token, strict=strict))
    print("---")
    print_probe_results(results)
    print("---")
    code = exit_code_for_results(results)
    print("RESULT: PASS" if code == 0 else "RESULT: FAIL")
    return code


if __name__ == "__main__":
    sys.exit(main())
