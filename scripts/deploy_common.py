"""Shared deploy/smoke helpers for VPS scripts (TG-GH-6)."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def notify_enabled() -> bool:
    return os.environ.get("LIMA_DEPLOY_NOTIFY", "1").strip().lower() not in {"0", "false", "no"}


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


def notify_telegram_vps(ssh: Any, message: str, *, event_type: str = "deploy") -> bool:
    """Run notify_ops_telegram.py on VPS (requires .env Telegram vars)."""
    if not notify_enabled():
        print("deploy_notify_skipped LIMA_DEPLOY_NOTIFY=0")
        return False
    payload = json.dumps({"message": message[:900], "type": event_type}, ensure_ascii=False)
    b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 scripts/notify_ops_telegram.py --b64 {b64}"
    )
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=45)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    ok = "notify_ok" in out
    print(f"telegram_notify_{event_type}={'ok' if ok else 'fail'} {out[:120]}")
    return ok


def notify_deploy_success(
    ssh: Any,
    label: str,
    *,
    service: str = "",
    health: str = "",
    detail: str = "",
) -> bool:
    return notify_telegram_vps(
        ssh,
        format_deploy_ok(label, service=service, health=health, detail=detail),
        event_type="deploy",
    )


def notify_smoke_success(ssh: Any, label: str, *, detail: str = "") -> bool:
    return notify_telegram_vps(
        ssh,
        format_smoke_ok(label, detail=detail),
        event_type="smoke",
    )
