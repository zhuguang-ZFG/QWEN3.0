"""Admin alert rules management endpoints (extracted from admin_api)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()
_log = logging.getLogger(__name__)

_ALERT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "alert_rules.json"
_ALERT_RULES_LOCK = asyncio.Lock()

_ALLOWED_CONDITIONS = {"gt", "lt", "eq"}
_ALLOWED_METRICS = {"error_rate", "latency_ms", "fallback_rate", "request_count"}


def _read_alert_rules() -> list[dict]:
    if not _ALERT_RULES_PATH.exists():
        return []
    try:
        data = json.loads(_ALERT_RULES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_alert_rules(rules: list[dict]) -> None:
    _ALERT_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ALERT_RULES_PATH.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@router.get("/api/alerts/rules", dependencies=[Depends(verify_admin)])
async def admin_alert_rules_list():
    """List all alert rules."""
    return {"rules": _read_alert_rules()}


@router.post("/api/alerts/rules", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_alert_rules_create(body: dict):
    """Create a new alert rule."""
    condition = body.get("condition", "gt")
    if condition not in _ALLOWED_CONDITIONS:
        raise HTTPException(422, f"Invalid condition: {condition!r} (allowed: {_ALLOWED_CONDITIONS})")
    metric = body.get("metric", "error_rate")
    if metric not in _ALLOWED_METRICS:
        raise HTTPException(422, f"Invalid metric: {metric!r} (allowed: {_ALLOWED_METRICS})")
    threshold = body.get("threshold", 0.5)
    if not isinstance(threshold, (int, float)):
        raise HTTPException(422, f"threshold must be a number, got {type(threshold).__name__}")
    window_sec = body.get("window_sec", 300)
    if not isinstance(window_sec, (int, float)) or window_sec < 10:
        raise HTTPException(422, "window_sec must be >= 10")

    async with _ALERT_RULES_LOCK:
        rules = _read_alert_rules()
        rule_id = f"alert-{int(time.time())}-{len(rules)}"
        rule = {
            "rule_id": rule_id,
            "name": body.get("name", "Untitled"),
            "metric": metric,
            "condition": condition,
            "threshold": threshold,
            "window_sec": int(window_sec),
            "enabled": body.get("enabled", True),
            "notify": body.get("notify", []),
            "created_at": time.time(),
        }
        rules.append(rule)
        _write_alert_rules(rules)
    _log.info("admin: created alert rule %s", rule_id)
    return {"ok": True, "rule": rule}


@router.put("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_alert_rules_update(rule_id: str, body: dict):
    """Update an existing alert rule."""
    async with _ALERT_RULES_LOCK:
        rules = _read_alert_rules()
        for rule in rules:
            if rule.get("rule_id") == rule_id:
                for key in ("name", "metric", "condition", "threshold", "window_sec", "enabled", "notify"):
                    if key in body:
                        rule[key] = body[key]
                _write_alert_rules(rules)
                _log.info("admin: updated alert rule %s", rule_id)
                return {"ok": True, "rule": rule}
    raise HTTPException(404, f"Alert rule '{rule_id}' not found")


@router.delete("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_alert_rules_delete(rule_id: str):
    """Delete an alert rule."""
    async with _ALERT_RULES_LOCK:
        rules = _read_alert_rules()
        new_rules = [r for r in rules if r.get("rule_id") != rule_id]
        if len(new_rules) == len(rules):
            raise HTTPException(404, f"Alert rule '{rule_id}' not found")
        _write_alert_rules(new_rules)
    _log.info("admin: deleted alert rule %s", rule_id)
    return {"ok": True, "deleted": rule_id}
