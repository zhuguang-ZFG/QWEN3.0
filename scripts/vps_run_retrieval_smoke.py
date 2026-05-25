#!/usr/bin/env python3
"""Run retrieval trace smoke on LiMa VPS over SSH."""

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
import urllib.request

PROD = {
    "routing_engine.py", "routing_classifier.py", "routing_selector.py",
    "routing_executor.py", "http_caller.py", "health_tracker.py",
    "retrieval_injection.py",
}


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


def request(method, url, headers=None, body=None, timeout=90):
    payload = None
    headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


base = "http://127.0.0.1:8080"
api_key = read_env("LIMA_API_KEY", "lima-local")
admin_token = read_env("LIMA_ADMIN_TOKEN", "")
query = "Explain how routing_engine.py selects backends using health_tracker.py"

chat_status, _chat_raw = request(
    "POST",
    base + "/v1/chat/completions",
    headers={"Authorization": "Bearer " + api_key},
    body={
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 64,
        "temperature": 0,
        "stream": False,
    },
)
print("chat_status", chat_status)

if admin_token:
    trace_status, trace_raw = request(
        "GET",
        base + "/admin/api/retrieval-traces",
        headers={"Authorization": "Bearer " + admin_token},
    )
    print("trace_source", "admin")
else:
    trace_status, trace_raw = request(
        "GET",
        base + "/v1/ops/metrics",
        headers={"Authorization": "Bearer " + api_key},
    )
    print("trace_source", "ops")
print("trace_status", trace_status)

if trace_status != 200:
    print("smoke_token", "prod_retrieval_trace_fail")
    raise SystemExit(1)

traces = json.loads(trace_raw)
if isinstance(traces, dict):
    traces = traces.get("retrieval_traces", [])
print("trace_count", len(traces))

hit = False
for trace in traces:
    blob = trace.get("injected_text", "") or ""
    blob += " " + " ".join(str(x) for x in trace.get("query_entities", []) or [])
    for item in trace.get("reranked_results", []) or []:
        if isinstance(item, dict):
            blob += " " + str(item.get("path", ""))
    if any(name in blob for name in PROD):
        hit = True
        chars = trace.get("injected_chars") or len(trace.get("injected_text", "") or "")
        print("trace_hit_chars", chars)
        print("trace_entities", (trace.get("query_entities") or [])[:5])
        break

print("prod_hit", hit)
token = "prod_retrieval_trace_ok" if chat_status == 200 and hit else "prod_retrieval_trace_fail"
print("smoke_token", token)
raise SystemExit(0 if token.endswith("_ok") else 1)
""")


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"SSH key not found: {KEY}", file=sys.stderr)
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30)

    remote_path = f"{REMOTE}/scripts/_smoke_retrieval_trace_once.py"
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
    time.sleep(20)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out.strip())
    if err.strip():
        print("stderr:", err.strip()[:500])
    code = stdout.channel.recv_exit_status()
    ssh.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
