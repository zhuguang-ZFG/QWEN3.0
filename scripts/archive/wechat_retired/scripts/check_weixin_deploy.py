#!/usr/bin/env python3
"""Audit VPS + local WeChat LiMa deploy."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = os.environ.get("LIMA_REMOTE_DIR", "/opt/lima-router")
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "channel_gateway/keyword_router.py",
    "channel_gateway/branding.py",
    "channel_gateway/media_inbound.py",
    "channel_gateway/service.py",
    "mimo_stt.py",
    "routes/channel_gateway.py",
]

ENV_KEYS = [
    "WECHAT_BRIDGE_ENABLED",
    "LIMA_CHANNEL_TOOLS",
    "LIMA_CHANNEL_AUTO_GUEST_BIND",
    "LIMA_WECHAT_SIDECAR_TOKEN",
    "LIMA_CHANNEL_ID_SALT",
    "MIMO_TTS_KEY",
    "LIMA_CHANNEL_VOICE_REPLY",
    "LIMA_CHANNEL_INVITE_QR",
    "MIMO_API_KEY",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 30) -> str:
    _i, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return (out + ("\n" + err if err.strip() else "")).strip()


def _read_env_remote(ssh: paramiko.SSHClient) -> dict[str, str]:
    raw = _run(ssh, f"grep -E '^({'|'.join(ENV_KEYS)})=' {REMOTE}/.env 2>/dev/null || true")
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def check_vps() -> list[str]:
    issues: list[str] = []
    ok: list[str] = []

    if not os.path.isfile(KEY):
        issues.append(f"SSH key missing: {KEY}")
        return issues

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    if active == "active":
        ok.append(f"lima-router: {active}")
    else:
        issues.append(f"lima-router not active: {active}")

    port = _run(ssh, "ss -tlnp | grep ':8080 ' || true")
    if "8080" in port:
        ok.append("port 8080 listening")
    else:
        issues.append("port 8080 not listening")

    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health 2>/dev/null || echo FAIL")
    if health.startswith("FAIL") or not health:
        issues.append("GET /health failed")
    else:
        ok.append(f"/health: {health[:80]}")

    env = _read_env_remote(ssh)
    if env.get("WECHAT_BRIDGE_ENABLED") == "1":
        ok.append("WECHAT_BRIDGE_ENABLED=1")
    else:
        issues.append(f"WECHAT_BRIDGE_ENABLED={env.get('WECHAT_BRIDGE_ENABLED', 'missing')}")

    token = env.get("LIMA_WECHAT_SIDECAR_TOKEN", "")
    if token:
        ok.append("LIMA_WECHAT_SIDECAR_TOKEN set")
    else:
        issues.append("LIMA_WECHAT_SIDECAR_TOKEN missing")

    mimo = env.get("MIMO_TTS_KEY") or env.get("MIMO_API_KEY")
    if mimo:
        ok.append("MiMo key present (STT/TTS)")
    else:
        issues.append("MIMO_TTS_KEY / MIMO_API_KEY missing — voice STT/TTS degraded")

    if _run(ssh, "which ffmpeg 2>/dev/null").strip():
        ok.append("ffmpeg installed")
    else:
        issues.append("ffmpeg not on PATH — WeChat silk voice may fail")

    for rel in REQUIRED_FILES:
        path = f"{REMOTE}/{rel}"
        exists = _run(ssh, f"test -f {path} && echo yes || echo no").strip()
        if exists != "yes":
            issues.append(f"missing remote file: {rel}")
            continue
        local = ROOT / rel
        if local.is_file():
            lhash = _run(ssh, f"md5sum {path} 2>/dev/null | cut -d' ' -f1").strip()
            # local md5 via ssh on windows use certutil or python
            import hashlib
            rh = hashlib.md5(local.read_bytes()).hexdigest()
            if lhash and lhash != rh:
                issues.append(f"hash mismatch (not deployed?): {rel}")
            else:
                ok.append(f"file ok: {rel}")

    py_check = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 -c \""
        "from channel_gateway.keyword_router import normalize_guest_text; "
        "from channel_gateway.branding import BRAND_SITE; "
        "import mimo_stt; "
        "assert normalize_guest_text('菜单')=='/menu'; "
        "assert 'donglilicao' in BRAND_SITE; "
        "print('import_ok')\" 2>&1",
        timeout=45,
    )
    if "import_ok" in py_check:
        ok.append("Python imports + keyword + branding OK")
    else:
        issues.append(f"Python import check failed: {py_check[:300]}")

    if token:
        ch = _run(
            ssh,
            f"curl -sf -H 'Authorization: Bearer {token}' "
            f"http://127.0.0.1:8080/channel/v1/wechat/health 2>/dev/null || echo FAIL",
        )
        if ch.startswith("FAIL"):
            issues.append("channel /wechat/health failed")
        elif '"enabled": true' in ch.replace(" ", "") or '"enabled":true' in ch:
            ok.append(f"channel health: {ch[:100]}")
        else:
            issues.append(f"channel disabled or bad response: {ch[:120]}")

        smoke_py = ROOT / "scripts" / "_audit_keyword_remote.py"
        smoke_py.write_text(
            "import json, time, urllib.request\n"
            f"token = {json.dumps(token)}\n"
            "body = json.dumps({\n"
            "  'message_id': 'audit-kw-' + str(int(time.time())),\n"
            "  'sender_id': 'audit-kw',\n"
            "  'conversation_id': 'c',\n"
            "  'text': '官网',\n"
            "  'timestamp': 1,\n"
            "}).encode()\n"
            "req = urllib.request.Request(\n"
            "  'http://127.0.0.1:8080/channel/v1/wechat/message',\n"
            "  data=body,\n"
            "  headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},\n"
            "  method='POST',\n"
            ")\n"
            "data = json.loads(urllib.request.urlopen(req, timeout=60).read())\n"
            "text = (data.get('reply') or {}).get('text', '')\n"
            "assert data.get('ok') and 'donglilicao' in text, data\n"
            "print('keyword_ok')\n",
            encoding="utf-8",
        )
        sftp = ssh.open_sftp()
        sftp.put(str(smoke_py), f"{REMOTE}/_audit_keyword.py")
        sftp.close()
        kw = _run(
            ssh,
            f"cd {REMOTE} && /usr/local/bin/python3.10 _audit_keyword.py 2>&1",
            timeout=90,
        )
        try:
            smoke_py.unlink()
        except OSError:
            pass
        if "keyword_ok" in kw:
            ok.append("live POST 官网 -> donglilicao.com")
        else:
            issues.append(f"keyword smoke failed: {kw[:250]}")

    ssh.close()
    print("=== VPS OK ===")
    for line in ok:
        print("  ", line)
    if issues:
        print("=== VPS ISSUES ===")
        for line in issues:
            print("  ", line)
    return issues


def check_local() -> list[str]:
    issues: list[str] = []
    ok: list[str] = []

    lima = os.environ.get("LIMA_CHANNEL_BASE_URL", "http://127.0.0.1:8080")
    try:
        with urllib.request.urlopen(lima + "/health", timeout=5) as resp:
            ok.append(f"local tunnel {lima}/health -> {resp.status}")
    except Exception as exc:
        issues.append(f"local {lima}/health unreachable ({exc}) — start tunnel or set LIMA_CHANNEL_BASE_URL")

    procs = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
            "Where-Object { $_.CommandLine -match 'hermes_weixin_lima_bridge' } | "
            "Measure-Object | Select-Object -ExpandProperty Count",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    count = (procs.stdout or "").strip()
    if count and count != "0":
        ok.append(f"weixin bridge python process(es): {count}")
    else:
        issues.append("hermes_weixin_lima_bridge not running locally")

    bridge = ROOT / "scripts" / "hermes_weixin_lima_bridge.py"
    if bridge.is_file():
        text = bridge.read_text(encoding="utf-8")
        if "show_typing" in text and "keyword_router" not in text:
            ok.append("local bridge has typing_helper")
        if "normalize_guest_text" not in text:
            pass  # keyword is on VPS channel only

    print("=== LOCAL ===")
    for line in ok:
        print("  ", line)
    for line in issues:
        print("  ", line)
    return issues


def main() -> int:
    print(f"VPS {SERVER} {REMOTE}\n")
    vps_issues = check_vps()
    print()
    local_issues = check_local()
    all_issues = vps_issues + local_issues
    if all_issues:
        print(f"\nSUMMARY: {len(all_issues)} issue(s) — fix before WeChat smoke")
        return 1
    print("\nSUMMARY: deploy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
