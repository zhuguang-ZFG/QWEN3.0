#!/usr/bin/env python3
"""Probe NewAPI: status, env, Redis, Kimi smoke, Claude cache_read."""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

UA = "LiMaNewAPICacheProbe/1.1"
HOST = os.environ.get("LIMA_JDCLOUD_SERVER", "117.72.118.95")


def http_json(url: str, *, bearer: str = "", body: dict | None = None, timeout: float = 30) -> tuple[int, dict]:
    headers = {"User-Agent": UA}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw[:400]}
    except OSError as exc:
        return 0, {"detail": str(exc)}


def resolve_token(cli: str) -> str:
    if cli.strip():
        return cli.strip()
    env = os.environ.get("NEWAPI_API_KEY", "").strip()
    if env:
        return env
    cfg = Path.home() / ".kimi-code" / "config.toml"
    if not cfg.is_file():
        return ""
    m = re.search(r'\[providers\.newapi\][\s\S]*?api_key\s*=\s*"([^"]+)"', cfg.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def jdcloud_password() -> str:
    pw = (os.environ.get("LIMA_JDCLOUD_SSH_PASS") or os.environ.get("JDCLOUD_SSH_PASSWORD") or "").strip()
    if pw:
        return pw
    vps = Path(r"D:\Downloads\VPS.txt")
    if not vps.is_file():
        return ""
    for line in vps.read_text(encoding="utf-8", errors="replace").splitlines():
        if HOST in line and "\u5bc6\u7801" in line:
            for sep in ("\u5bc6\u7801\uff1a", "\u5bc6\u7801:"):
                if sep in line:
                    return line.split(sep, 1)[-1].strip()
    return ""


_SERVER_ENV_SCRIPT = r"""
cd /opt/newapi || exit 2
CID=$(docker-compose ps -q new-api 2>/dev/null | head -1); [ -z "$CID" ] && CID=$(docker ps -qf name=new-api | head -1)
[ -z "$CID" ] && { echo ENV_FAIL; exit 1; }
echo CRYPTO_LEN=$(docker exec "$CID" printenv CRYPTO_SECRET 2>/dev/null | wc -c)
echo STREAMING_TIMEOUT=$(docker exec "$CID" printenv STREAMING_TIMEOUT 2>/dev/null)
echo MEMORY_CACHE_ENABLED=$(docker exec "$CID" printenv MEMORY_CACHE_ENABLED 2>/dev/null)
# Host Redis (compose redis removed). Password from container REDIS_CONN_STRING.
RURL=$(docker exec "$CID" printenv REDIS_CONN_STRING 2>/dev/null || true)
RPASS=$(RURL="$RURL" python3 -c "import os,re,urllib.parse;u=os.environ.get('RURL','');m=re.match(r'redis://:([^@]+)@',u);print(urllib.parse.unquote(m.group(1)) if m else '')")
if [ -n "$RPASS" ]; then
  echo REDIS_PING=$(redis-cli -a "$RPASS" --no-auth-warning PING 2>/dev/null || echo FAIL)
  echo REDIS_KEYSPACE=$(redis-cli -a "$RPASS" --no-auth-warning INFO keyspace 2>/dev/null | tr -d '\r' | grep -E '^db' | head -1)
else
  echo REDIS_PING=$(redis-cli PING 2>/dev/null || echo FAIL)
fi
"""


def _score_server_env(vals: dict[str, str]) -> tuple[int, list[str]]:
    lines: list[str] = []
    fails = 0
    clen = int(vals.get("CRYPTO_LEN", "0") or 0)
    # wc -c counts newline → tolerate len-1
    if clen > 8:
        lines.append(f"OK    CRYPTO_SECRET set (approx_len={clen})")
    else:
        lines.append("FAIL  CRYPTO_SECRET empty")
        fails += 1
    stream, mem, ping = (
        vals.get("STREAMING_TIMEOUT", ""),
        vals.get("MEMORY_CACHE_ENABLED", "").lower(),
        vals.get("REDIS_PING", ""),
    )
    for ok, msg_ok, msg_bad in (
        (stream == "600", "OK    STREAMING_TIMEOUT=600", f"FAIL  STREAMING_TIMEOUT={stream!r}"),
        (mem in ("true", "1", "yes"), f"OK    MEMORY_CACHE_ENABLED={mem}", f"FAIL  MEMORY_CACHE_ENABLED={mem!r}"),
        (ping == "PONG", "OK    Redis PING", f"FAIL  Redis PING={ping!r}"),
    ):
        lines.append(msg_ok if ok else msg_bad)
        fails += 0 if ok else 1
    if vals.get("REDIS_KEYSPACE"):
        lines.append(f"INFO  redis keyspace: {vals['REDIS_KEYSPACE'][:120]}")
    return fails, lines


def check_server_env() -> tuple[int, list[str]]:
    try:
        import paramiko

        from scripts.deploy_common import configure_ssh_host_keys
    except ImportError:
        return 0, ["WARN  server-env skipped (paramiko not installed)"]
    password = jdcloud_password()
    if not password:
        return 0, ["WARN  server-env skipped (set LIMA_JDCLOUD_SSH_PASS or VPS.txt)"]
    client = paramiko.SSHClient()
    configure_ssh_host_keys(client)
    try:
        client.connect(HOST, username="root", password=password, timeout=25, allow_agent=False, look_for_keys=False)
    except OSError as exc:
        return 1, [f"FAIL  server-ssh -> {exc}"]
    _, stdout, _ = client.exec_command(_SERVER_ENV_SCRIPT, timeout=60)
    out = stdout.read().decode("utf-8", "replace")
    client.close()
    vals = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return _score_server_env(vals)


def usage_cache_read(body: dict) -> int | None:
    usage = body.get("usage") or {}
    if "cache_read_input_tokens" in usage:
        return int(usage.get("cache_read_input_tokens") or 0)
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict) and "cached_tokens" in details:
        return int(details.get("cached_tokens") or 0)
    nested = usage.get("input_tokens_details")
    if isinstance(nested, dict) and "cache_read_input_tokens" in nested:
        return int(nested.get("cache_read_input_tokens") or 0)
    return None


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NewAPI cache health probe")
    p.add_argument("--host", default=os.environ.get("LIMA_NEWAPI_HOST", "api.donglicao.com"))
    p.add_argument("--claude-port", type=int, default=3001)
    p.add_argument("--token", default="")
    p.add_argument("--skip-server", action="store_true")
    p.add_argument("--skip-chat", action="store_true", help="skip Kimi smoke")
    p.add_argument(
        "--claude-cache",
        action="store_true",
        help="opt-in Claude dual-call cache_read check (burns upstream quota)",
    )
    p.add_argument("--require-sidecar", action="store_true")
    return p.parse_args()


def _check_public_status(base: str, token: str) -> int:
    status, body = http_json(f"{base}/api/status", bearer=token)
    ok = status == 200 and body.get("success") is True
    print(f"{'OK' if ok else 'FAIL'}  public /api/status -> {status}")
    if not ok:
        print(f"      {repr(body)[:200]}")
        return 1
    return 0


def _check_sidecar(port: int, *, require: bool) -> int:
    ss, sb = http_json(f"http://127.0.0.1:{port}/api/status")
    if ss == 200 and sb.get("success") is True:
        print(f"OK    claude-sidecar :{port}")
        return 0
    if require:
        print(f"FAIL  claude-sidecar :{port} -> {ss}")
        return 1
    print(f"SKIP  claude-sidecar :{port} (optional)")
    return 0


def _check_kimi_smoke(base: str, token: str) -> int:
    chat = f"{base}/v1/chat/completions"
    ks, kb = http_json(
        chat,
        bearer=token,
        body={
            "model": "kimi-for-coding-highspeed",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        },
        timeout=90,
    )
    if ks == 200 and kb.get("choices"):
        print(f"OK    kimi smoke model={kb.get('model')}")
        return 0
    print(f"FAIL  kimi smoke -> {ks} {repr(kb)[:160]}")
    if ks == 404:
        print("      hint: Kimi base_url = https://api.kimi.com/coding (no /v1)")
    return 1


def _check_claude_cache(base: str, token: str) -> tuple[int, int]:
    chat = f"{base}/v1/chat/completions"
    pad = ("You are a careful coding assistant. " * 80).strip()
    payload = {
        "model": "claude-opus-4-6",
        "messages": [
            {"role": "system", "content": pad},
            {"role": "user", "content": "Reply with exactly: ok"},
        ],
        "max_tokens": 16,
    }
    c1, _ = http_json(chat, bearer=token, body=payload, timeout=180)
    c2, b2 = http_json(chat, bearer=token, body=payload, timeout=180)
    if c1 != 200 or c2 != 200:
        print(f"FAIL  claude dual-call -> {c1}/{c2}")
        return 1, 0
    cr = usage_cache_read(b2)
    if cr is None:
        print("WARN  claude #2: no cache_read field")
        return 0, 1
    if cr > 0:
        print(f"OK    claude cache_read_input_tokens={cr}")
        return 0, 0
    print("WARN  claude #2: cache_read=0")
    return 0, 1


def main() -> int:
    args = _parse_args()
    failures = warnings = 0
    token = resolve_token(args.token)
    base = f"https://{args.host}"

    failures += _check_public_status(base, token)
    failures += _check_sidecar(args.claude_port, require=args.require_sidecar)

    if not args.skip_server:
        n, lines = check_server_env()
        failures += n
        for line in lines:
            print(line)

    if not args.skip_chat:
        if not token:
            print("FAIL  need --token / NEWAPI_API_KEY / ~/.kimi-code providers.newapi")
            failures += 1
        else:
            failures += _check_kimi_smoke(base, token)
            if not args.claude_cache:
                print("SKIP  claude cache_read (pass --claude-cache to enable; burns quota)")
            else:
                f, w = _check_claude_cache(base, token)
                failures += f
                warnings += w

    print(f"---\nresult: failures={failures} warnings={warnings}")
    print("Doc: docs/ops/NEWAPI_KIMI_CODE_CACHE_CN.md")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
