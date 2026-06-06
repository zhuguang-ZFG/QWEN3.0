#!/usr/bin/env python3
"""Deploy post-review LiMa bundle to VPS (security + P3 splits + retrieval)."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

import os
import subprocess
import sys
import time
from pathlib import Path

import paramiko
from deploy_common import configure_ssh_host_keys

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "server.py",
    "server_bootstrap.py",
    "http_body_limit.py",
    "routing_engine.py",
    "routing_classifier.py",
    "routing_selector.py",
    "routing_executor.py",
    "route_post_process.py",
    "identity_guard.py",
    "response_cleaner.py",
    "http_stream.py",
    "lima_context.py",
    "speculative.py",
    "converters/anthropic_format.py",
    "context_pipeline/retrieval_corpus.py",
    "context_pipeline/production_index.py",
    "context_pipeline/retrieval_injection.py",
    "context_pipeline/code_scanner.py",
    "context_pipeline/entity_extraction.py",
    "context_pipeline/graph_retrieval.py",
    "context_pipeline/reranking.py",
    "context_pipeline/retrieval_trace.py",
    "routes/admin.py",
    "routes/admin_api.py",
    "routes/admin_auth.py",
    "routes/admin_backends_crud.py",
    "routes/admin_client_keys.py",
    "routes/admin_state.py",
    "routes/admin_ui.py",
    "routes/request_tracking.py",
    "routes/chat_handler.py",
    "routes/chat_handler_dispatch.py",
    "routes/chat_endpoints.py",
    "routes/anthropic_messages_handler.py",
    "routes/anthropic_vision_sse.py",
    "routes/tool_forward.py",
    "routes/tool_forward_stream.py",
    "admin.html",
    # 新增: FC 工具模块 (DIRS handles lima_fc_tools/ *.py auto-upload)
    # 新增: 代码执行沙箱 (DIRS handles sandbox/ *.py auto-upload)
]

DIRS = ["local_retrieval", "lima_fc_tools", "sandbox"]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
    try:
        out = stdout.read().decode("utf-8", errors="replace")
    except Exception as exc:
        _log(f"[warn] stdout read failed: {exc}")
        out = ""
    try:
        err = stderr.read().decode("utf-8", errors="replace")
    except Exception as exc:
        _log(f"[warn] stderr read failed: {exc}")
        err = ""
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run_smokes() -> None:
    scripts = Path(__file__).resolve().parent
    py = sys.executable
    critical_steps = [
        ("health", [py, "-c", _health_probe_script()]),
        ("retrieval", [py, str(scripts / "vps_run_retrieval_smoke.py")]),
        ("messages", [py, str(scripts / "vps_run_messages_smoke.py")]),
    ]
    for name, cmd in critical_steps:
        _log(f"running smoke: {name}")
        subprocess.run(cmd, check=True, cwd=str(scripts.parent))

    # OpenCode E2E — warning-only, does not block deploy on failure
    _log("running smoke: opencode_e2e")
    try:
        result = subprocess.run(
            [py, str(scripts / "vps_opencode_e2e_verify.py"), "--quick"],
            cwd=str(scripts.parent), timeout=180,
        )
        if result.returncode != 0:
            _log(f"opencode_e2e warning: exit={result.returncode} (non-blocking)")
    except subprocess.TimeoutExpired:
        _log("opencode_e2e warning: timed out after 180s (non-blocking)")
    except Exception as exc:
        _log(f"opencode_e2e warning: {exc} (non-blocking)")


def _health_probe_script() -> str:
    return r"""
import os, sys, paramiko
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))
from deploy_common import configure_ssh_host_keys
KEY=os.path.expanduser('~/.ssh/id_ed25519')
ssh=paramiko.SSHClient()
configure_ssh_host_keys(ssh)
ssh.connect('47.112.162.80', username='root', key_filename=KEY, timeout=60)
i,o,e=ssh.exec_command('curl -sf http://127.0.0.1:8080/health')
body=o.read().decode()
code=o.channel.recv_exit_status()
print('health_status', code, body[:80])
ssh.close()
sys.exit(0 if code == 0 else 1)
""".strip()


def main() -> None:
    run_smoke = "--smoke" in sys.argv
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("no VPS backup (rollback via GitHub)")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            _log.debug("deploy_vps_bundle: optional dependency or operation failed", exc_info=True)
        data = local.read_bytes()
        with sftp.file(remote, "wb") as handle:
            handle.write(data)
            handle.flush()
        _log(f"uploaded {rel} ({len(data)} bytes)")

    for dirname in DIRS:
        local_dir = base / dirname
        remote_dir = f"{REMOTE}/{dirname}"
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            _log.debug("deploy_vps_bundle: optional dependency or operation failed", exc_info=True)
        for name in os.listdir(local_dir):
            if name.endswith(".py"):
                sftp.put(str(local_dir / name), f"{remote_dir}/{name}")
                _log(f"uploaded {dirname}/{name}")
    sftp.close()

    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    time.sleep(3)
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(2)
    _run(
        ssh,
        (
            f"cd {REMOTE} && "
            "nohup /usr/local/bin/python3.10 server.py "
            "> /var/log/lima-server.log 2>&1 < /dev/null & echo $!"
        ),
        timeout=10,
    )
    time.sleep(6)

    port = _run(ssh, "ss -tlnp | grep 8080")
    if not port:
        _log("FAILED: " + _run(ssh, "tail -30 /var/log/lima-server.log"))
        ssh.close()
        sys.exit(1)

    _log("Server UP on 8080")
    ssh.close()

    if run_smoke:
        _run_smokes()
        _log("smoke_token vps_bundle_ok")


if __name__ == "__main__":
    main()
