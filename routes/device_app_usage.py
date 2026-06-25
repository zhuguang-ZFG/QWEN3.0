"""Account-level usage estimates for device app tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import ok

router = APIRouter(tags=["device-app-stats"])

_USAGE_ESTIMATES: dict[str, dict[str, Any]] = {
    "chat": {"tokens": 500, "cost": 0.0015},
    "draw_generated": {"tokens": 1500, "cost": 0.0045},
    "write_text": {"tokens": 1000, "cost": 0.003},
}


def _usage_start(days: int) -> str:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _capability_from_intent(intent: str) -> str:
    intent_lower = (intent or "").lower()
    if "draw" in intent_lower or "image" in intent_lower:
        return "draw_generated"
    if "write" in intent_lower or "text" in intent_lower or "run_path" in intent_lower:
        return "write_text"
    return "chat"


def _estimate_usage(intent: str) -> tuple[int, float]:
    capability = _capability_from_intent(intent)
    est = _USAGE_ESTIMATES.get(capability, _USAGE_ESTIMATES["chat"])
    return int(est["tokens"]), float(est["cost"])


def _load_completed_tasks(account_id: Any, start: str) -> list[Any]:
    with connect() as conn:
        return list(
            conn.execute(
                """
                SELECT id, intent, created_at
                FROM v2_task
                WHERE account_id=? AND status='completed' AND created_at>=?
                ORDER BY created_at DESC
                """,
                (account_id, start),
            ).fetchall()
        )


def _aggregate_usage(rows: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    daily: dict[str, dict[str, Any]] = {}
    by_capability: dict[str, dict[str, Any]] = {}
    total_tokens = 0
    total_cost = 0.0

    for row in rows:
        intent = row["intent"] or "chat"
        tokens, cost = _estimate_usage(intent)
        date = (row["created_at"] or "")[:10]
        capability = _capability_from_intent(intent)

        total_tokens += tokens
        total_cost += cost

        day = daily.setdefault(date, {"date": date, "tokens": 0, "requests": 0, "cost": 0.0})
        day["tokens"] += tokens
        day["requests"] += 1
        day["cost"] += cost

        cap = by_capability.setdefault(capability, {"capability": capability, "requests": 0, "tokens": 0, "cost": 0.0})
        cap["requests"] += 1
        cap["tokens"] += tokens
        cap["cost"] += cost

    summary = {
        "totalTokens": total_tokens,
        "totalRequests": len(rows),
        "estimatedCost": round(total_cost, 4),
    }
    return summary, sorted(daily.values(), key=lambda x: x["date"]), list(by_capability.values())


def _paginate_details(rows: list[Any], page: int, page_size: int) -> list[dict[str, Any]]:
    start = (page - 1) * page_size
    return [
        {
            "date": (row["created_at"] or "")[:10],
            "type": _capability_from_intent(row["intent"] or "chat"),
            "tokens": _estimate_usage(row["intent"] or "chat")[0],
            "cost": round(_estimate_usage(row["intent"] or "chat")[1], 4),
        }
        for row in rows[start : start + page_size]
    ]


@router.get("/stats/usage")
async def usage_stats(
    days: int = Query(30, ge=1, le=90),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Return estimated token/cost usage for the account's completed tasks."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    rows = _load_completed_tasks(account["id"], _usage_start(days))
    summary, daily, by_capability = _aggregate_usage(rows)
    details = _paginate_details(rows, page, page_size)

    return ok(
        {
            "days": days,
            "accountId": account["id"],
            "summary": summary,
            "daily": daily,
            "byCapability": by_capability,
            "details": {
                "items": details,
                "page": page,
                "pageSize": page_size,
                "total": len(rows),
            },
        }
    )
