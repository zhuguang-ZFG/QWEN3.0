#!/usr/bin/env python3
"""Run /v1/messages tool-route smoke on LiMa VPS over SSH (CTX-003)."""

from __future__ import annotations

import os
import sys
import textwrap
import time

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

REMOTE_SCRIPT = textwrap.dedent("""
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/opt/lima-router")

from converters.anthropic_format import (
    PREFLIGHT_MARKER,
    anthropic_system_text,
    convert_messages_anthropic_to_openai,
    inject_anthropic_body_preflight,
    inject_anthropic_context_preflight,
)


def read_env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    if value:
        return value
    for path in ("/etc/environment", ".env"):
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return default


def request(method, url, headers=None, body=None, timeout=120):
    payload = None
    headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


body = {
    "model": "lima-1.3",
    "max_tokens": 256,
    "system": "Working directory: /opt/lima-router",
    "messages": [
        {
            "role": "user",
            "content": "Fix routing_engine.py after SyntaxError: invalid syntax",
        }
    ],
    "tools": [
        {
            "name": "Read",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ],
}
openai_msgs = convert_messages_anthropic_to_openai(body["messages"])
inject_anthropic_context_preflight(openai_msgs, body)
inject_anthropic_body_preflight(body, openai_msgs)

system_text = anthropic_system_text(body)
preflight_ok = PREFLIGHT_MARKER in system_text
openai_ok = (
    openai_msgs
    and openai_msgs[0].get("role") == "system"
    and PREFLIGHT_MARKER in str(openai_msgs[0].get("content", ""))
)
print("preflight_body_ok", preflight_ok)
print("preflight_openai_ok", openai_ok)
print("system_chars", len(system_text))

base = "http://127.0.0.1:8080"
api_key = read_env("LIMA_API_KEY", "lima-local")
headers = {
    "Authorization": "Bearer " + api_key,
    "User-Agent": "claude-code/1.0",
}

messages_status, raw = request(
    "POST",
    base + "/v1/messages",
    headers=headers,
    body=body,
)
print("messages_status", messages_status)

response_type = ""
stop_reason = ""
try:
    data = json.loads(raw)
    response_type = data.get("type", "")
    if response_type == "message":
        stop_reason = data.get("stop_reason", "")
        print("stop_reason", stop_reason)
    elif response_type == "error":
        err = data.get("error", {})
        print("error_type", err.get("type", ""))
except Exception as exc:
    print("parse_error", type(exc).__name__)
    print("raw_head", raw[:300])

live_ok = messages_status == 200 and response_type in ("message", "error")
print("live_ok", live_ok)

token = (
    "ctx003_messages_ok"
    if preflight_ok and openai_ok and live_ok
    else "ctx003_messages_fail"
)
print("smoke_token", token)
raise SystemExit(0 if token.endswith("_ok") else 1)
""")


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"SSH key not found: {KEY}", file=sys.stderr)
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    remote_path = f"{REMOTE}/scripts/_smoke_messages_once.py"
    sftp = ssh.open_sftp()
    try:
        sftp.mkdir(f"{REMOTE}/scripts")
    except OSError:
        pass
    with sftp.file(remote_path, "w") as handle:
        handle.write(REMOTE_SCRIPT)
    sftp.close()

    _stdin, stdout, stderr = ssh.exec_command(
        f"cd {REMOTE} && /usr/local/bin/python3.10 {remote_path}"
    )
    time.sleep(45)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out.strip())
    if err.strip() and "Traceback" in err:
        print("stderr:", err.strip()[:800])
    code = stdout.channel.recv_exit_status()
    ssh.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
