#!/usr/bin/env python3
"""Add nginx proxy for POST /gitee/webhook on chat.donglicao.com."""

from __future__ import annotations

import os
import sys

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SITE_CONF = "/etc/nginx/conf.d/chat.donglicao.com.conf"

GITEE_BLOCK = """
    location ^~ /gitee/ {
        limit_req zone=webhook burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
"""


def _run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _i, o, e = ssh.exec_command(cmd)
    return (o.read() + e.read()).decode("utf-8", "replace").strip()


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    content = _run(ssh, f"cat {SITE_CONF}")
    if "location ^~ /gitee/" in content:
        print("nginx gitee block already present")
    else:
        marker = "    location ^~ /github/ {"
        if marker not in content:
            marker = "    location ^~ /telegram/ {"
        if marker not in content:
            ssh.close()
            sys.exit("nginx marker not found")
        content = content.replace(marker, GITEE_BLOCK + "\n" + marker, 1)
        escaped = content.replace("'", "'\"'\"'")
        _run(ssh, f"cp {SITE_CONF} {SITE_CONF}.bak.gitee-webhook")
        _run(ssh, f"printf '%s' '{escaped}' > {SITE_CONF}")

    test = _run(ssh, "nginx -t 2>&1")
    print(test)
    if "successful" not in test:
        ssh.close()
        return 1

    reload_out = _run(ssh, "systemctl reload nginx 2>&1")
    if reload_out:
        print(reload_out)
    print("nginx_gitee_webhook_ok")
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
