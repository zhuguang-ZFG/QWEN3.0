"""Shared deploy/smoke helpers for VPS scripts."""

from __future__ import annotations

import os
from typing import Any

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def notify_enabled() -> bool:
    return os.environ.get("LIMA_DEPLOY_NOTIFY", "1").strip().lower() not in {"0", "false", "no"}


def configure_ssh_host_keys(ssh: paramiko.SSHClient) -> None:
    """Load known_hosts and reject unknown SSH host keys."""
    ssh.load_system_host_keys()
    known_hosts = os.environ.get("LIMA_DEPLOY_KNOWN_HOSTS")
    if known_hosts:
        ssh.load_host_keys(known_hosts)
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())


def format_deploy_ok(label: str, *, service: str = "", health: str = "", detail: str = "") -> str:
    lines = [f"Deploy OK: {label}"]
    if service:
        lines.append(f"service={service}")
    if health:
        lines.append(f"health={health[:160]}")
    if detail:
        lines.append(detail[:240])
    return "\n".join(lines)


def format_smoke_ok(label: str, *, detail: str = "") -> str:
    text = f"Smoke OK: {label}"
    if detail:
        text += f"\n{detail[:240]}"
    return text


def notify_operator_vps(ssh: Any, message: str, *, event_type: str = "deploy") -> bool:
    """Operator push notifications are retired; keep deploy call sites stable."""
    _ = ssh
    if not notify_enabled():
        print("deploy_notify_skipped LIMA_DEPLOY_NOTIFY=0")
        return False
    print(f"deploy_notify_retired event={event_type} detail={message[:120]}")
    return False


def notify_deploy_success(
    ssh: Any,
    label: str,
    *,
    service: str = "",
    health: str = "",
    detail: str = "",
) -> bool:
    return notify_operator_vps(
        ssh,
        format_deploy_ok(label, service=service, health=health, detail=detail),
        event_type="deploy",
    )


def notify_smoke_success(ssh: Any, label: str, *, detail: str = "") -> bool:
    return notify_operator_vps(
        ssh,
        format_smoke_ok(label, detail=detail),
        event_type="smoke",
    )
