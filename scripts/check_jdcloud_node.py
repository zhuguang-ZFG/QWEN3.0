#!/usr/bin/env python3
"""Read-only JDCloud node smoke for LiMa ops capacity planning."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import deploy_config  # noqa: E402
from scripts.deploy_common import configure_ssh_host_keys  # noqa: E402

DEFAULT_HOST = deploy_config.JDCLOUD_SERVER
DEFAULT_USER = deploy_config.JDCLOUD_USER
ROLE = "secondary_probe_monitoring"


REMOTE_CHECK = r"""
set -u
disk=$(df -Pm / | awk 'NR==2 {print $4}')
mem=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
loadavg=$(cut -d' ' -f1-3 /proc/loadavg)
lima_probe_timer=$(systemctl is-active lima-probe.timer 2>/dev/null || true)
lima_probe_service=$(systemctl is-active lima-probe.service 2>/dev/null || true)
prometheus_service=$(systemctl is-active prometheus 2>/dev/null || true)
chat_health=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' https://chat.donglicao.com/health 2>/dev/null || echo curl_failed)
browser_health=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8092/health 2>/dev/null || echo curl_failed)
browser_ready=$(curl -sS -m 20 -o /dev/null -w '%{http_code}' http://127.0.0.1:8092/ready 2>/dev/null || echo curl_failed)
browser_render=$(curl -sS -m 45 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8092/render -H 'Content-Type: application/json' -d '{"url":"https://example.com","wait_ms":500}' 2>/dev/null || echo curl_failed)
echo "disk_free_mb=$disk"
echo "mem_available_mb=$mem"
echo "loadavg=$loadavg"
echo "lima_probe_timer=${lima_probe_timer:-unknown}"
echo "lima_probe_service=${lima_probe_service:-unknown}"
echo "prometheus_service=${prometheus_service:-unknown}"
echo "chat_health_http_code=$chat_health"
echo "chat_prometheus_http_code=not_configured"
echo "browser_health_http_code=$browser_health"
echo "browser_ready_http_code=$browser_ready"
echo "browser_render_http_code=$browser_render"
"""


def _scalar(value: str) -> int | str:
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    return stripped or "unknown"


def parse_remote_report(output: str) -> dict[str, int | str]:
    report: dict[str, int | str] = {}
    for raw in output.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        report[key.strip()] = _scalar(value)
    return report


def build_result(host: str, user: str, report: dict[str, int | str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": report.get("chat_health_http_code") == 200,
        "host": host,
        "user": user,
        "role": ROLE,
    }
    result.update(report)
    return result


def run_remote_check(
    host: str,
    user: str,
    key_path: str | None,
    password: str | None,
    timeout: int,
) -> dict[str, int | str]:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    connect_kwargs: dict[str, Any] = {"username": user, "timeout": timeout}
    if key_path:
        connect_kwargs["key_filename"] = key_path
    if password:
        connect_kwargs["password"] = password
    ssh.connect(host, **connect_kwargs)
    try:
        _stdin, stdout, stderr = ssh.exec_command(REMOTE_CHECK, timeout=timeout)
        code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace").strip()
    finally:
        ssh.close()
    if code != 0:
        raise RuntimeError(f"JDCloud read-only check failed: {err or out.strip()}")
    return parse_remote_report(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only JDCloud LiMa ops node smoke")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--key-path", default=deploy_config.DEPLOY_KEY_PATH)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)
    password = deploy_config.jdcloud_password()

    try:
        report = run_remote_check(args.host, args.user, args.key_path, password, args.timeout)
        result = build_result(args.host, args.user, report)
        exit_code = 0 if result["ok"] else 2
    except Exception as exc:
        result = {
            "ok": False,
            "host": args.host,
            "user": args.user,
            "role": ROLE,
            "error_class": type(exc).__name__,
            "error": str(exc),
        }
        exit_code = 3
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"JDCloud {result['host']} role={result['role']} ok={str(result['ok']).lower()}")
        print(f"capacity disk_free_mb={result.get('disk_free_mb')} mem_available_mb={result.get('mem_available_mb')}")
        print(
            "services "
            f"lima_probe_timer={result.get('lima_probe_timer')} "
            f"lima_probe_service={result.get('lima_probe_service')} "
            f"prometheus_service={result.get('prometheus_service')}"
        )
        print(f"chat_health_http_code={result.get('chat_health_http_code')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
