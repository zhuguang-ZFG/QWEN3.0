#!/usr/bin/env python3
"""Diagnose google_flash_lite health/degradation on LiMa VPS."""

from __future__ import annotations

import json
import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
BACKEND = "google_flash_lite"


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 90) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    py = "/usr/local/bin/python3.10"
    probe_cmd = (
        f"cd {REMOTE} && {py} -c \""
        "import json, http_caller; "
        "print(json.dumps({'probe': http_caller.probe('google_flash_lite')}, default=str))"
        "\""
    )
    tracker_cmd = (
        f"cd {REMOTE} && {py} -c \""
        "import json, health_tracker; "
        "b='google_flash_lite'; "
        "print(json.dumps({"
        "'health': health_tracker.get_health(b), "
        "'state': health_tracker.get_backend_state(b), "
        "'cooldown': health_tracker.get_cooldown_remaining(b)"
        "}, default=str))"
        "\""
    )
    metrics_cmd = (
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a; "
        f"curl -sf -H \"Authorization: Bearer $LIMA_API_KEY\" http://127.0.0.1:8080/v1/ops/metrics"
    )
    status_cmd = (
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a; "
        f"curl -sf -H \"Authorization: Bearer $LIMA_API_KEY\" http://127.0.0.1:8080/v1/status"
    )
    log_cmd = (
        "journalctl -u lima-router -n 500 --no-pager 2>/dev/null | "
        f"grep -E 'google_flash_lite|Backend google_flash_lite' | tail -25 || true"
    )
    proxy_cmd = f"cd {REMOTE} && grep -E '^GFW_PROXY=' .env 2>/dev/null | head -1 || true"

    probe_code, probe_out = _run(ssh, probe_cmd, timeout=120)
    tracker_code, tracker_out = _run(ssh, tracker_cmd, timeout=60)
    metrics_code, metrics_out = _run(ssh, metrics_cmd, timeout=30)
    status_code, status_out = _run(ssh, status_cmd, timeout=30)
    _, log_out = _run(ssh, log_cmd, timeout=30)
    _, proxy_out = _run(ssh, proxy_cmd, timeout=15)

    ssh.close()

    print(f"probe_code={probe_code}")
    print(f"probe={probe_out[:400]}")
    print(f"gfw_proxy={proxy_out}")

    health = ""
    if tracker_code == 0 and tracker_out:
        try:
            tracker = json.loads(tracker_out.splitlines()[-1])
            health = str(tracker.get("health") or "")
            print(f"tracker={json.dumps(tracker, ensure_ascii=False)[:500]}")
        except json.JSONDecodeError:
            print(f"tracker_raw={tracker_out[:300]}")

    if metrics_code == 0 and metrics_out:
        try:
            metrics = json.loads(metrics_out)
            backends = metrics.get("backends") or {}
            err = backends.get("error_summary") or {}
            gf_err = err.get(BACKEND)
            print(
                f"metrics degraded={backends.get('degraded')} "
                f"dead={backends.get('dead')} "
                f"{BACKEND}_error={json.dumps(gf_err, ensure_ascii=False) if gf_err else 'none'}"
            )
        except json.JSONDecodeError:
            print(f"metrics_parse_error raw={metrics_out[:200]}")
    else:
        print(f"metrics_code={metrics_code}")

    if status_code == 0 and status_out:
        try:
            status = json.loads(status_out)
            cb = (status.get("circuit_breakers") or {}).get(BACKEND) or {}
            print(f"circuit_breaker={cb}")
        except json.JSONDecodeError:
            print(f"status_parse_error raw={status_out[:200]}")

    if log_out:
        print("recent_logs:")
        print(log_out[:1500])

    ok = probe_code == 0 and health in ("healthy", "")
    print("diag_ok" if ok else "diag_degraded_or_unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
