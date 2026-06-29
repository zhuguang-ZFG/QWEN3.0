"""LiMa device app asset library routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from device_gateway.task_creation import project_to_motion_task_async
from device_workflow.state import TaskState
from device_logic.access import require_device_access, require_device_control
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, new_id, now, ok, read_body, str_field
from routes.device_app_task_store import insert_task_row
from xiaozhi_drawing.svg_validator import sanitize_svg_markup

router = APIRouter(prefix="/device/v1/app", tags=["device-app-assets"])

_ASSET_CATEGORIES = frozenset({"text", "image", "svg", "template"})
_DIFFICULTIES = frozenset({"easy", "medium", "hard"})


def _asset_payload(row: Any) -> dict[str, Any]:
    return {
        "assetId": row["id"],
        "title": row["title"],
        "category": row["category"],
        "content": row["content"],
        "previewUrl": row["preview_url"] or "",
        "tags": json.loads(row["tags"] or "[]"),
        "difficulty": row["difficulty"],
        "useCount": row["use_count"],
        "createdAt": row["created_at"],
        "status": row["status"],
    }


def _asset_params(category: str, content: str, body_params: dict[str, Any]) -> dict[str, Any]:
    if category == "text":
        params: dict[str, Any] = {"text": content}
    else:
        params = {"prompt": content}
    if isinstance(body_params, dict):
        params.update(body_params)
    return params


def _asset_capability(category: str) -> str:
    return "write_text" if category == "text" else "draw_generated"


async def _build_asset_task(
    device_id: str, category: str, content: str, body_params: dict[str, Any], request_id: str
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    capability = _asset_capability(category)
    params = _asset_params(category, content, body_params)
    task = await project_to_motion_task_async(
        device_id,
        {"capability": capability, "params": params, "source": "api", "entrypoint": "app_api"},
        request_id,
    )
    task_error = task.get("error")
    if isinstance(task_error, dict):
        reason = task_error.get("reason") or task_error.get("code") or "task build failed"
        return None, err(4003, str(reason), 400)
    task["app_capability"] = capability
    return task, None


def _asset_status(task: dict[str, Any]) -> str:
    if task.get("workflow_state") == TaskState.WAITING_APPROVAL.value:
        return "pending"
    return "approved"


@router.get("/assets")
async def list_assets(
    category: str = "",
    tag: str = "",
    difficulty: str = "",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    authorization: str = Header(default=""),
):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    clauses = ["status='active'"]
    params: list[Any] = []
    if category:
        clauses.append("category=?")
        params.append(category)
    if difficulty:
        clauses.append("difficulty=?")
        params.append(difficulty)
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")

    where = " AND ".join(clauses)
    count_sql = f"SELECT COUNT(*) AS cnt FROM v2_asset_library WHERE {where}"
    list_sql = f"SELECT * FROM v2_asset_library WHERE {where} ORDER BY use_count DESC, created_at DESC LIMIT ? OFFSET ?"

    with connect() as conn:
        total = conn.execute(count_sql, params).fetchone()["cnt"]
        rows = conn.execute(list_sql, [*params, limit, offset]).fetchall()

    return ok({"assets": [_asset_payload(row) for row in rows], "total": total, "limit": limit, "offset": offset})


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_asset_library WHERE id=? AND status='active'", (asset_id,)).fetchone()
        if row is None:
            return err(404, "asset not found", 404)
        conn.execute("UPDATE v2_asset_library SET use_count=use_count+1 WHERE id=?", (asset_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM v2_asset_library WHERE id=?", (asset_id,)).fetchone()

    return ok(_asset_payload(row))


def _prepare_asset_payload(body: dict[str, Any]) -> tuple[str, str, str, str, list[str], JSONResponse | None]:
    """校验并清洗 asset 创建参数；返回 (title, category, content, difficulty, tags, error)。"""
    title = str_field(body, "title")
    category = str_field(body, "category")
    content = str_field(body, "content")
    if not title or not category or not content:
        return "", "", "", "", [], err(400, "title, category and content are required", 400)
    if category not in _ASSET_CATEGORIES:
        return "", "", "", "", [], err(400, f"invalid category: {category}", 400)

    if category == "svg" and content:
        sanitized = sanitize_svg_markup(content)
        if not sanitized.ok:
            return "", "", "", "", [], err(400, f"invalid svg: {sanitized.error}", 400)
        content = sanitized.cleaned

    difficulty = str_field(body, "difficulty") or "easy"
    if difficulty not in _DIFFICULTIES:
        return "", "", "", "", [], err(400, f"invalid difficulty: {difficulty}", 400)

    tags = body.get("tags", [])
    if not isinstance(tags, list):
        return "", "", "", "", [], err(400, "tags must be an array", 400)

    return title, category, content, difficulty, [str(t) for t in tags], None


@router.post("/assets")
async def create_asset(request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    title, category, content, difficulty, tags, error = _prepare_asset_payload(body)
    if error is not None:
        return error

    asset_id = new_id()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_asset_library
            (id, title, category, content, preview_url, tags, difficulty, created_at, use_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'active')
            """,
            (
                asset_id,
                title,
                category,
                content,
                str_field(body, "previewUrl") or body.get("preview_url", ""),
                json.dumps(tags, ensure_ascii=False),
                difficulty,
                now(),
            ),
        )
        conn.commit()

    return ok({"assetId": asset_id, "title": title, "status": "created"})


@router.post("/assets/{asset_id}/render")
async def render_asset(asset_id: str, request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    device_id = str_field(body, "deviceId", "device_id")
    if not device_id:
        return err(400, "deviceId is required", 400)

    with connect() as conn:
        denied = require_device_control(conn, account, device_id)
        if denied:
            return denied
        row = conn.execute("SELECT * FROM v2_asset_library WHERE id=? AND status='active'", (asset_id,)).fetchone()
        if row is None:
            return err(404, "asset not found", 404)

    body_params = body.get("params")
    if not isinstance(body_params, dict):
        body_params = {}

    from device_logic.gateway import dispatch_or_enqueue

    task, error = await _build_asset_task(device_id, row["category"], row["content"], body_params, new_id())
    if error:
        return error
    assert task is not None

    status = _asset_status(task)
    dispatch = await dispatch_or_enqueue(device_id, task)
    insert_task_row(device_id, account, task, "api", status, {"assetId": asset_id}, task.get("params", {}))

    return ok(
        {
            "taskId": task["task_id"],
            "assetId": asset_id,
            "status": status,
            "dispatchStatus": dispatch.get("dispatchStatus"),
            "queueDepth": dispatch.get("queueDepth"),
            "sent": dispatch.get("sent"),
        }
    )
