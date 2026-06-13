#!/usr/bin/env python3
"""Run VPS eval smoke: health preflight + quick coding eval slice."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.deploy_common import KEY, REMOTE, SERVER, configure_ssh_host_keys

import paramiko

HEALTH_WAIT_S = 180
HEALTH_POLL_S = 5


def _exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


def wait_health(ssh: paramiko.SSHClient) -> tuple[bool, str]:
    deadline = time.time() + HEALTH_WAIT_S
    while time.time() < deadline:
        code, out, err = _exec(ssh, "curl -sS -m 5 http://127.0.0.1:8080/health")
        if code == 0 and "ok" in out.lower():
            return True, out
        time.sleep(HEALTH_POLL_S)
    return False, err or out or "health timeout"


def main() -> int:
    ssh = paramiko.SSHClient()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)
    try:
        print("=== import check ===")
        code, out, err = _exec(
            ssh,
            f"cd {REMOTE} && python3.10 -c 'import eval_pinned_call, routing_engine; print(\"import_ok\")'",
        )
        print(out or err)
        if code != 0:
            print("IMPORT FAILED")
            return 1

        print("=== wait health ===")
        ok, detail = wait_health(ssh)
        print("health_ok=", ok, detail[:200])
        if not ok:
            _exec(ssh, "journalctl -u lima-router -n 20 --no-pager")
            _, logs, _ = _exec(ssh, "journalctl -u lima-router -n 20 --no-pager")
            print(logs)
            return 1

        print("=== eval preflight ===")
        code, out, err = _exec(
            ssh,
            f"cd {REMOTE} && python3.10 -c "
            "\"from eval_preflight import check_eval_health; "
            "ok,d=check_eval_health('http://127.0.0.1:8080'); "
            "print('preflight', ok, d)\"",
        )
        print(out or err)
        if code != 0 or "preflight True" not in (out or ""):
            return 1

        print("=== quick eval scnet_qwen30b x1 ===")
        code, out, err = _exec(
            ssh,
            f"cd {REMOTE} && python3.10 scripts/eval_coding_backends.py "
            "--backends scnet_qwen30b --max-cases 1",
        )
        print(out)
        if err:
            print("stderr:", err[:500])
        if code != 0:
            return 1

        print("=== optional FRP backend scnet_large_ds_flash x1 ===")
        code2, out2, err2 = _exec(
            ssh,
            f"cd {REMOTE} && LIMA_EVAL_TOPOLOGY=1 "
            "LIMA_EVAL_VIA_ROUTER_URL=http://127.0.0.1:8088 "
            "python3.10 scripts/eval_coding_backends.py "
            "--backends scnet_large_ds_flash --max-cases 1",
        )
        print(out2)
        if err2:
            print("stderr:", err2[:500])
        if code2 != 0:
            print("FRP eval slice failed (non-fatal if Windows router down)")
            return 0

        print("SMOKE OK: eval pinned + optional FRP slice")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
