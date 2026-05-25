#!/usr/bin/env python3
"""Deploy production retrieval wiring to LiMa VPS."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    # Server bootstrap
    "server.py",
    "server_bootstrap.py",
    # Routing split (routing_engine imports these)
    "routing_engine.py",
    "routing_classifier.py",
    "routing_selector.py",
    "routing_executor.py",
    "route_post_process.py",
    # Identity / streaming
    "identity_guard.py",
    "response_cleaner.py",
    "http_stream.py",
    # Production retrieval stack
    "context_pipeline/retrieval_corpus.py",
    "context_pipeline/production_index.py",
    "context_pipeline/retrieval_injection.py",
    "context_pipeline/code_scanner.py",
    "context_pipeline/entity_extraction.py",
    "context_pipeline/graph_retrieval.py",
    "context_pipeline/reranking.py",
    "context_pipeline/retrieval_trace.py",
    # Admin trace endpoint
    "routes/admin_api.py",
]

DIRS = ["local_retrieval"]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
    try:
        out = stdout.read().decode("utf-8", errors="replace")
    except Exception:
        out = ""
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run_smoke() -> None:
    import subprocess

    script = Path(__file__).resolve().parent / "vps_run_retrieval_smoke.py"
    _log("running retrieval smoke...")
    subprocess.run([sys.executable, str(script)], check=True)


def main() -> None:
    run_smoke = "--smoke" in sys.argv
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
            pass
        sftp.put(str(local), remote)
        _log(f"uploaded {rel}")

    for dirname in DIRS:
        local_dir = base / dirname
        remote_dir = f"{REMOTE}/{dirname}"
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass
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
        _log("FAILED: " + _run(ssh, "tail -20 /var/log/lima-server.log"))
        ssh.close()
        sys.exit(1)

    _log("Server UP on 8080")
    ssh.close()

    if run_smoke:
        _run_smoke()


if __name__ == "__main__":
    main()
