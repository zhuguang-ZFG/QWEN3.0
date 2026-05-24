"""Structured status output for LiMa operations.

The status helpers return compact human-readable and JSON snapshots without
requiring a TUI framework. Values are redacted before formatting so accidental
secret-like strings do not leak through operator output.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

VALID_STATUSES = {"ok", "warn", "error"}
STATUS_MARKERS = {"ok": "  ", "warn": "! ", "error": "X "}


def _redact_text(value: object) -> str:
    text = str(value)
    try:
        from session_memory.redact import sanitize_for_display

        return sanitize_for_display(text)
    except ImportError:
        text = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)
        text = re.sub(r"Bearer\s+\S{12,}", "Bearer [REDACTED]", text)
        text = re.sub(
            r"(?i)(api[_-]?key|password|secret|token|cookie)=([^&\s]+)",
            r"\1=[REDACTED]",
            text,
        )
        return text


@dataclass
class StatusRow:
    name: str
    value: str
    status: str = "ok"  # ok | warn | error
    detail: str = ""

    def __post_init__(self) -> None:
        self.name = _redact_text(self.name)
        self.value = _redact_text(self.value)
        self.detail = _redact_text(self.detail)
        normalized = str(self.status).lower()
        self.status = normalized if normalized in VALID_STATUSES else "warn"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class StatusTable:
    title: str
    rows: list[StatusRow]

    def __post_init__(self) -> None:
        self.title = _redact_text(self.title)


def format_status_text(tables: list[StatusTable]) -> str:
    lines = []
    for table in tables:
        lines.append(f"-- {table.title} --")
        name_width = max(len(row.name) for row in table.rows) if table.rows else 10
        value_width = max(len(row.value) for row in table.rows) if table.rows else 20
        for row in table.rows:
            marker = STATUS_MARKERS.get(row.status, "! ")
            name = row.name.ljust(name_width)
            value = row.value.ljust(value_width)
            detail = f"  ({row.detail})" if row.detail else ""
            lines.append(f"  {marker}{name}  {value}{detail}")
        lines.append("")
    return "\n".join(lines)


def format_status_json(tables: list[StatusTable]) -> str:
    return json.dumps(
        {table.title: [row.to_dict() for row in table.rows] for table in tables},
        ensure_ascii=False,
        indent=2,
    )


def collect_router_status() -> StatusTable:
    rows = [StatusRow(name="snapshot_ts", value=f"{time.time():.0f}", status="ok")]
    try:
        from health_tracker import get_health_map

        health_map = get_health_map()
        healthy = sum(1 for value in health_map.values() if value == "healthy")
        degraded = sum(1 for value in health_map.values() if value == "degraded")
        dead = sum(1 for value in health_map.values() if value == "dead")
        rows.append(
            StatusRow(
                name="backends",
                value=f"{len(health_map)} total",
                status="ok" if dead == 0 else "warn",
                detail=f"{healthy} healthy, {degraded} degraded, {dead} dead",
            )
        )
    except Exception as exc:
        rows.append(
            StatusRow(
                name="backend_health",
                value="unavailable",
                status="warn",
                detail=str(exc),
            )
        )

    try:
        from observability.metrics import get_metrics_snapshot

        snapshot = get_metrics_snapshot()
        rows.append(
            StatusRow(
                name="requests",
                value=str(snapshot.get("total_requests", 0)),
                status="ok",
            )
        )
    except Exception as exc:
        rows.append(
            StatusRow(
                name="observability",
                value="unavailable",
                status="warn",
                detail=str(exc),
            )
        )

    return StatusTable(title="Router", rows=rows)


def collect_memory_status() -> StatusTable:
    rows = []
    try:
        from session_memory.daemon import daemon_status

        daemon = daemon_status()
        running = bool(daemon.get("running"))
        rows.append(
            StatusRow(
                name="daemon",
                value="running" if running else "stopped",
                status="ok" if running else "warn",
            )
        )
        rows.append(StatusRow(name="inbox", value=str(daemon.get("inbox_dir", ""))))
    except Exception as exc:
        rows.append(
            StatusRow(
                name="daemon",
                value="unavailable",
                status="warn",
                detail=str(exc),
            )
        )
    return StatusTable(title="Memory", rows=rows)


def collect_keypool_status() -> StatusTable:
    rows = []
    try:
        from key_pool import pool_snapshot

        snapshot = pool_snapshot()
        providers = snapshot.get("providers", {})
        for name, provider_snapshot in sorted(providers.items()):
            total = provider_snapshot.get("total", 0)
            active = provider_snapshot.get("active", 0)
            blocked = provider_snapshot.get("blocked", 0)
            status = "ok" if active > 0 else ("warn" if total > 0 else "error")
            rows.append(
                StatusRow(
                    name=name,
                    value=f"{active}/{total} active",
                    status=status,
                    detail=f"{blocked} blocked" if blocked else "",
                )
            )
    except Exception as exc:
        rows.append(
            StatusRow(
                name="key_pool",
                value="unavailable",
                status="warn",
                detail=str(exc),
            )
        )
    return StatusTable(title="Key Pools", rows=rows)


def collect_all_status() -> list[StatusTable]:
    return [
        collect_router_status(),
        collect_memory_status(),
        collect_keypool_status(),
    ]


def print_status(fmt: str = "text") -> str:
    tables = collect_all_status()
    if fmt == "json":
        return format_status_json(tables)
    return format_status_text(tables)
