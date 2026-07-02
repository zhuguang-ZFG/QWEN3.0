"""Admin backends 主题路由 — 从 admin_api.py 拆出以控制行数。

为保持测试 ``patch.object(admin_api, "BACKENDS")`` 等兼容，路由函数体内
被 patch 的符号通过 ``import routes.admin_api as _a`` 延迟访问，
使 monkeypatch 替换 ``admin_api`` 模块属性即可生效（与拆分前行为一致）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_backends import describe_backend
from routes.admin_state import stats_context

router = APIRouter()


def _backend_status_info(name: str) -> dict:
    """Build admin-backend status compatible with the old circuit-breaker shape."""
    import health_state
    import health_tracker

    quality = health_state.get_backend_quality(name)
    total = quality["total_requests"]
    errors = quality["empty_count"] + quality["error_msg_count"]
    error_rate = f"{errors / total:.1%}" if total > 0 else "0.0%"
    return {
        "state": "open" if health_tracker.is_cooled_down(name) else "closed",
        "total_calls": total,
        "error_rate": error_rate,
    }


def _admin_actor(req: Request) -> str:
    """Extract admin actor identity for audit logging (AUDIT-5-O4)."""
    try:
        actor = req.cookies.get("lima_admin_user") or ""
        if actor:
            return actor
        return req.client.host if req.client else "unknown"
    except Exception:
        return "unknown"


@router.get("/api/backends", dependencies=[Depends(verify_admin)])
async def admin_backends():
    _stats, _lock, backend_enabled = stats_context()
    import routes.admin_api as _a

    backends_list = []
    for name, cfg in _a.BACKENDS.items():
        enabled = backend_enabled.get(name, True)
        backends_list.append(
            describe_backend(
                name,
                cfg,
                enabled=enabled,
                status_info=_backend_status_info(name),
            )
        )
    return backends_list


@router.post("/api/backends", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_add_backend(req: Request):
    _stats, _lock, backend_enabled = stats_context()
    import routes.admin_api as _a

    body = await req.json()
    name = body.get("name", "").strip()
    url = body.get("url", "").strip()
    key = body.get("key", "").strip()
    model = body.get("model", name)
    fmt = body.get("fmt", "openai")
    auth = body.get("auth", "").strip()
    if not auth:
        auth = "x-api-key" if fmt == "anthropic" else "bearer"
    if not name or not url:
        raise HTTPException(400, "name and url required")
    if not _a._is_safe_backend_url(url):
        raise HTTPException(400, f"backend URL must be a public HTTPS endpoint: {url}")
    if _a.has_backend(name):
        raise HTTPException(409, f"backend '{name}' already exists")
    _a.add_backend(
        name,
        {
            "url": url,
            "key": key,
            "model": model,
            "fmt": fmt,
            "auth": auth,
            "tier": body.get("tier", ""),
            "caps": body.get("caps", []),
        },
    )
    backend_enabled[name] = True
    try:
        from tool_gateway.audit import audit_event

        audit_event("admin_backend_added", backend=name, url=url, model=model, fmt=fmt, actor=_admin_actor(req))
    except Exception as exc:
        logging.getLogger(__name__).debug("admin audit (add) failed: %s", exc)
    try:
        test_result = _a.test_backend_sync(name)
        return {"ok": True, "message": f"backend '{name}' added", "test": test_result}
    except Exception as exc:
        backend_enabled[name] = False
        return {
            "ok": True,
            "message": f"backend '{name}' added but DISABLED (test failed: {exc})",
            "enabled": False,
        }


@router.delete("/api/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_delete_backend(name: str):
    _stats, _lock, backend_enabled = stats_context()
    import routes.admin_api as _a

    if not _a.has_backend(name):
        raise HTTPException(404, f"backend '{name}' not found")
    _a.remove_backend(name)
    backend_enabled.pop(name, None)
    try:
        from tool_gateway.audit import audit_event

        audit_event("admin_backend_deleted", backend=name)
    except Exception as exc:
        logging.getLogger(__name__).debug("admin audit (delete) failed: %s", exc)
    return {"ok": True, "message": f"backend '{name}' deleted"}


@router.post("/api/backends/{name}/toggle", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_toggle_backend(name: str):
    _stats, _lock, backend_enabled = stats_context()
    import routes.admin_api as _a

    if name not in _a.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    current = backend_enabled.get(name, True)
    backend_enabled[name] = not current
    try:
        from tool_gateway.audit import audit_event

        audit_event("admin_backend_toggled", backend=name, enabled=not current)
    except Exception as exc:
        logging.getLogger(__name__).debug("admin audit (toggle) failed: %s", exc)
    return {"ok": True, "enabled": not current}


@router.post("/api/backends/{name}/test", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_test_backend(name: str):
    import routes.admin_api as _a

    if name not in _a.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    return _a.test_backend_sync(name)
