"""LiMa native device app statistics routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, ok

router = APIRouter(prefix="/device/v1/app", tags=["device-app-stats"])

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _period_start(period: str) -> str:
    days = PERIOD_DAYS.get(period, 7)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_ms_expr() -> str:
    return """
        (julianday(completed_at) - julianday(started_at)) * 86400000.0
    """.strip()


def _device_overview(conn, device_id: str, start: str) -> dict[str, Any]:
    duration_expr = _duration_ms_expr()
    return conn.execute(
        f"""
        SELECT
            COUNT(*) as total_tasks,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_tasks,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_tasks,
            SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled_tasks,
            AVG(CASE WHEN status='completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
                THEN {duration_expr} ELSE NULL END) as avg_duration_ms,
            SUM(CASE WHEN status='completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
                THEN {duration_expr} ELSE 0 END) as total_duration_ms
        FROM v2_task
        WHERE device_id=? AND created_at>=?
        """,
        (device_id, start),
    ).fetchone()


def _most_used_capability(conn, device_id: str, start: str) -> str | None:
    row = conn.execute(
        """
        SELECT intent, COUNT(*) as cnt
        FROM v2_task
        WHERE device_id=? AND created_at>=?
        GROUP BY intent
        ORDER BY cnt DESC, intent ASC
        LIMIT 1
        """,
        (device_id, start),
    ).fetchone()
    return row["intent"] if row else None


def _daily_breakdown(conn, device_id: str, start: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DATE(created_at) as date, COUNT(*) as count,
               SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed
        FROM v2_task
        WHERE device_id=? AND created_at>=?
        GROUP BY DATE(created_at)
        ORDER BY date ASC
        """,
        (device_id, start),
    ).fetchall()
    return [{"date": r["date"], "total": r["count"], "completed": r["completed"]} for r in rows]


def _hourly_pattern(conn, device_id: str, start: str) -> list[int]:
    rows = conn.execute(
        """
        SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour, COUNT(*) as count
        FROM v2_task
        WHERE device_id=? AND created_at>=?
        GROUP BY hour
        ORDER BY hour
        """,
        (device_id, start),
    ).fetchall()
    pattern = [0] * 24
    for row in rows:
        pattern[row["hour"]] = row["count"]
    return pattern


def _account_device_stats(conn, account_id: str, start: str) -> dict[str, Any]:
    return conn.execute(
        """
        SELECT
            COUNT(DISTINCT device_id) as total_devices,
            COUNT(DISTINCT CASE WHEN EXISTS(
                SELECT 1 FROM v2_task t
                WHERE t.device_id = d.device_id AND t.created_at >= ?
            ) THEN d.device_id END) as active_devices
        FROM v2_device_binding d
        WHERE d.account_id=? AND d.status='active'
        """,
        (start, account_id),
    ).fetchone()


def _account_task_stats(conn, account_id: str, start: str) -> dict[str, Any]:
    duration_expr = _duration_ms_expr()
    return conn.execute(
        f"""
        SELECT
            COUNT(*) as total_tasks,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_tasks,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_tasks,
            AVG(CASE WHEN status='completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
                THEN {duration_expr} ELSE NULL END) as avg_duration_ms
        FROM v2_task
        WHERE account_id=? AND created_at>=?
        """,
        (account_id, start),
    ).fetchone()


def _account_device_ranking(conn, account_id: str, start: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT device_id, COUNT(*) as task_count
        FROM v2_task
        WHERE account_id=? AND created_at>=?
        GROUP BY device_id
        ORDER BY task_count DESC, device_id ASC
        LIMIT 10
        """,
        (account_id, start),
    ).fetchall()
    return [{"deviceId": r["device_id"], "taskCount": r["task_count"]} for r in rows]


@router.get("/devices/{device_id}/stats")
async def device_stats(
    device_id: str,
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    authorization: str = Header(default=""),
) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    start = _period_start(period)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        overview = _device_overview(conn, device_id, start)
        capability = _most_used_capability(conn, device_id, start)
        daily = _daily_breakdown(conn, device_id, start)
        hourly = _hourly_pattern(conn, device_id, start)

    total = overview["total_tasks"] or 0
    completed = overview["completed_tasks"] or 0
    failed = overview["failed_tasks"] or 0
    success_rate = round(completed / total * 100, 1) if total > 0 else 0.0

    return ok(
        {
            "period": period,
            "deviceId": device_id,
            "totalTasks": total,
            "completedTasks": completed,
            "failedTasks": failed,
            "cancelledTasks": overview["cancelled_tasks"] or 0,
            "successRate": success_rate,
            "totalDurationMs": round(overview["total_duration_ms"] or 0),
            "avgDurationMs": round(overview["avg_duration_ms"] or 0),
            "mostUsedCapability": capability,
            "dailyBreakdown": daily,
            "hourlyPattern": hourly,
        }
    )


@router.get("/stats/overview")
async def account_stats(
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    authorization: str = Header(default=""),
) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    start = _period_start(period)
    with connect() as conn:
        device_stats = _account_device_stats(conn, account["id"], start)
        task_stats = _account_task_stats(conn, account["id"], start)
        ranking = _account_device_ranking(conn, account["id"], start)

    total_tasks = task_stats["total_tasks"] or 0
    completed_tasks = task_stats["completed_tasks"] or 0
    success_rate = round(completed_tasks / max(total_tasks, 1) * 100, 1)

    return ok(
        {
            "period": period,
            "accountId": account["id"],
            "totalDevices": device_stats["total_devices"] or 0,
            "activeDevices": device_stats["active_devices"] or 0,
            "totalTasks": total_tasks,
            "completedTasks": completed_tasks,
            "failedTasks": task_stats["failed_tasks"] or 0,
            "successRate": success_rate,
            "avgDurationMs": round(task_stats["avg_duration_ms"] or 0),
            "deviceRanking": ranking,
        }
    )
