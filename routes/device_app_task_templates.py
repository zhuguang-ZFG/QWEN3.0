"""LiMa native device app task template routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from device_logic.access import is_owner, require_device_access, require_device_control
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, new_id, now, ok, read_body, str_field
from routes.device_app_task_payloads import task_row_payload
from routes.device_app_task_store import insert_task_row
from routes.device_app_tasks import APP_TASK_CAPABILITIES, APP_TASK_SOURCES, _build_app_gateway_task, _dispatch_or_wait

router = APIRouter(prefix="/device/v1/app", tags=["device-app-templates"])

_TEMPLATE_CATEGORIES = frozenset({"recent", "favorite", "custom"})


def _is_valid_capability(capability: str) -> bool:
    mapped = "draw_generated" if capability == "draw_image" else capability
    return mapped in APP_TASK_CAPABILITIES


def _template_payload(row) -> dict[str, Any]:
    return {
        "templateId": row["id"],
        "accountId": row["account_id"],
        "deviceId": row["device_id"],
        "name": row["name"],
        "capability": row["capability"],
        "params": json.loads(row["params"]) if row["params"] else {},
        "category": row["category"],
        "useCount": row["use_count"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _require_template_owner(account: dict[str, Any], row) -> JSONResponse | None:
    if row["account_id"] != account["id"]:
        return err(403, "Template does not belong to this account", 403)
    return None


@router.post("/tasks/templates")
async def create_task_template(request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    name = str_field(body, "name")
    capability = str_field(body, "capability", "intent")
    device_id = str_field(body, "deviceId", "device_id") or None
    category = str_field(body, "category") or "custom"
    params = body.get("params", {})

    if not name or not capability:
        return err(400, "name and capability are required", 400)
    if not _is_valid_capability(capability):
        return err(400, "unsupported capability", 400)
    if category not in _TEMPLATE_CATEGORIES:
        return err(400, "invalid category", 400)
    if not isinstance(params, dict):
        return err(400, "params must be an object", 400)

    with connect() as conn:
        if device_id:
            denied = require_device_access(conn, account, device_id)
            if denied:
                return denied
        created = now()
        template_id = new_id()
        conn.execute(
            """
            INSERT INTO v2_task_template
                (id, account_id, device_id, name, capability, params, category, use_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (template_id, account["id"], device_id, name, capability, json.dumps(params), category, created, created),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task_template WHERE id=?", (template_id,)).fetchone()
    return ok(_template_payload(row))


@router.get("/tasks/templates")
async def list_task_templates(
    device_id: str = "",
    category: str = "",
    limit: int = Query(20, ge=1, le=100),
    authorization: str = Header(default=""),
):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    clauses = ["account_id=?"]
    args: list[Any] = [account["id"]]
    if device_id:
        clauses.append("device_id=?")
        args.append(device_id)
    if category:
        clauses.append("category=?")
        args.append(category)
    args.append(limit)

    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM v2_task_template WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
            tuple(args),
        ).fetchall()
    return ok([_template_payload(row) for row in rows])


@router.post("/tasks/templates/{template_id}/execute")
async def execute_task_template(template_id: str, request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task_template WHERE id=?", (template_id,)).fetchone()
    if row is None:
        return err(404, "template not found", 404)
    denied = _require_template_owner(account, row)
    if denied:
        return denied

    device_id = str_field(body, "deviceId", "device_id") or row["device_id"]
    if not device_id:
        return err(400, "device_id is required", 400)

    source = str_field(body, "source") or "api"
    if source not in APP_TASK_SOURCES:
        return err(400, "invalid source", 400)

    with connect() as conn:
        denied = require_device_control(conn, account, device_id)
        if denied:
            return denied

    params = json.loads(row["params"]) if row["params"] else {}
    request_id = str_field(body, "requestId", "request_id")
    task, error = await _build_app_gateway_task(device_id, row["capability"], params, source, request_id)
    if error:
        return error
    assert task is not None

    dispatch, status = await _dispatch_or_wait(device_id, task, source, params)
    db_row = insert_task_row(device_id, account, task, source, status, body, params)

    with connect() as conn:
        conn.execute(
            "UPDATE v2_task_template SET use_count = use_count + 1, updated_at = ? WHERE id = ?",
            (now(), template_id),
        )
        conn.commit()

    data = task_row_payload(db_row)
    data.update(dispatch)
    data["task"] = task
    return ok(data)


@router.post("/tasks/{task_id}/save-as-template")
async def save_task_as_template(task_id: str, request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    name = str_field(body, "name")
    category = str_field(body, "category") or "custom"
    if not name:
        return err(400, "name is required", 400)
    if category not in _TEMPLATE_CATEGORIES:
        return err(400, "invalid category", 400)

    with connect() as conn:
        task_row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if task_row is None:
            return err(404, "task not found", 404)
        denied = require_device_access(conn, account, task_row["device_id"])
        if denied:
            return denied
        if task_row["account_id"] != account["id"] and not is_owner(conn, account, task_row["device_id"]):
            return err(403, "Task does not belong to this account", 403)

        created = now()
        template_id = new_id()
        params = task_row["params"] or "{}"
        conn.execute(
            """
            INSERT INTO v2_task_template
                (id, account_id, device_id, name, capability, params, category, use_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                template_id,
                account["id"],
                task_row["device_id"],
                name,
                task_row["intent"],
                params,
                category,
                created,
                created,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task_template WHERE id=?", (template_id,)).fetchone()
    return ok(_template_payload(row))
