"""Admin API: alert rule CRUD (in-memory panel state)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()

_ALERT_RULES: dict[str, dict[str, Any]] = {}


def iter_enabled_rules() -> list[dict[str, Any]]:
    """Return enabled alert rules for the evaluator."""
    return [rule for rule in _ALERT_RULES.values() if rule.get("enabled")]


@router.get("/api/alerts/rules", dependencies=[Depends(verify_admin)])
async def list_alert_rules():
    return {"rules": list(_ALERT_RULES.values())}


@router.post("/api/alerts/rules", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def create_alert_rule(req: Request):
    body = await req.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name required")
    rule_id = f"alert-{uuid.uuid4().hex[:8]}"
    rule = {
        "rule_id": rule_id,
        "name": name,
        "metric": body.get("metric", "error_rate"),
        "condition": body.get("condition", "gt"),
        "threshold": float(body.get("threshold", 0.5)),
        "window_sec": int(body.get("window_sec", 300)),
        "enabled": True,
        "created_at": time.time(),
    }
    _ALERT_RULES[rule_id] = rule
    return {"ok": True, "rule": rule}


@router.put("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def update_alert_rule(rule_id: str, req: Request):
    body = await req.json()
    rule = _ALERT_RULES.get(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    if "enabled" in body:
        rule["enabled"] = bool(body["enabled"])
    if "threshold" in body:
        rule["threshold"] = float(body["threshold"])
    if "name" in body:
        rule["name"] = body["name"]
    return {"ok": True, "rule": rule}


@router.delete("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def delete_alert_rule(rule_id: str):
    if rule_id not in _ALERT_RULES:
        raise HTTPException(404, "Rule not found")
    del _ALERT_RULES[rule_id]
    return {"ok": True, "rule_id": rule_id}
