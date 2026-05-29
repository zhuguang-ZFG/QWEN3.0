#!/usr/bin/env python3
"""Capture OpenClaw WeChat login QR from VPS (timeout, no wait for scan)."""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
REMOTE_OUT = "/opt/lima-router/data/openclaw_login_capture.txt"
LOCAL_HTML = Path(__file__).resolve().parent.parent / "data" / "openclaw_login_qr.html"
LOCAL_TXT = Path(__file__).resolve().parent.parent / "data" / "openclaw_login_capture.txt"


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


def _extract_urls(text: str) -> list[str]:
    patterns = [
        r"https://[^\s\]'\"]+",
        r"weixin://[^\s\]'\"]+",
        r"http://127\.0\.0\.1[^\s\]'\"]+",
    ]
    found: list[str] = []
    for pat in patterns:
        for m in re.findall(pat, text):
            u = m.rstrip(".,;)")
            if u not in found and ("qr" in u.lower() or "ilink" in u.lower() or "weixin" in u.lower() or len(u) > 40):
                found.append(u)
    return found


def _write_html(urls: list[str], raw: str) -> None:
    LOCAL_HTML.parent.mkdir(parents=True, exist_ok=True)
    links = "\n".join(
        f'<p class="box"><a href="{u}">{u}</a></p>' for u in urls[:5]
    ) or "<p>未从输出解析到 URL，见下方原始日志。</p>"
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>OpenClaw 微信扫码（多用户绑定）</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:sans-serif;max-width:560px;margin:1.5rem auto;padding:1rem;line-height:1.6}}
.box{{background:#f0f7ff;padding:1rem;border-radius:8px;word-break:break-all}}
pre{{font-size:0.8rem;overflow:auto;background:#f5f5f5;padding:0.75rem}}</style></head>
<body>
<h1>OpenClaw 微信扫码</h1>
<p>每人扫一次可新增一个账号；扫完后管理员在 VPS 执行 <code>openclaw pairing approve openclaw-weixin &lt;CODE&gt;</code>。</p>
<h2>扫码链接</h2>
{links}
<h2>原始输出</h2>
<pre>{raw[:4000].replace("<", "&lt;")}</pre>
</body></html>"""
    LOCAL_HTML.write_text(body, encoding="utf-8")


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"no SSH key: {KEY}", file=sys.stderr)
        return 1
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    print("=== restart gateway (free memory) ===")
    _run(ssh, "pkill -f 'openclaw channels login' 2>/dev/null; pkill -f openclaw-channels 2>/dev/null; true")
    time.sleep(2)
    _run(ssh, "systemctl restart lima-openclaw")
    time.sleep(35)
    print(_run(ssh, "systemctl is-active lima-openclaw; ss -tlnp | grep 18789 || true"))

    login_cmd = (
        "bash -lc 'set -a && source /opt/lima-router/.env && set +a && "
        "unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET && "
        "export OPENCLAW_STATE_DIR=/opt/lima-router/openclaw/state "
        "OPENCLAW_CONFIG_PATH=/opt/lima-router/openclaw/openclaw.json "
        "PATH=/root/.nvm/versions/node/v22.22.1/bin:$PATH && "
        f"timeout 40 openclaw channels login --channel openclaw-weixin --verbose 2>&1 | tee {REMOTE_OUT}'"
    )
    print("=== capture login QR (40s) ===")
    cap = _run(ssh, login_cmd, timeout=90)
    remote = _run(ssh, f"cat {REMOTE_OUT} 2>/dev/null || true", timeout=30)
    text = remote if remote.strip() else cap
    LOCAL_TXT.write_text(text, encoding="utf-8")
    urls = _extract_urls(text)
    _write_html(urls, text)

    sftp = ssh.open_sftp()
    try:
        sftp.put(str(LOCAL_HTML), "/opt/lima-router/data/openclaw_login_qr.html")
    except OSError:
        pass
    sftp.close()
    ssh.close()

    print(f"\nLocal HTML: {LOCAL_HTML}")
    print(f"Local log:  {LOCAL_TXT}")
    if urls:
        print("\n--- 扫码链接（请用微信打开/扫一扫）---")
        for u in urls:
            print(u)
    else:
        print("\nWARN: 未解析到 URL，请打开 HTML 查看原始终端输出")
    return 0 if urls else 2


if __name__ == "__main__":
    raise SystemExit(main())
