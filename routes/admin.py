"""routes/admin.py — LiMa 管理接口"""
import os
import sys
import json
import time
import threading
import subprocess
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

import smart_router
from routes.admin_auth import (
    SESSION_COOKIE,
    admin_session_value,
    get_admin_token,
    is_valid_admin_session,
    verify_admin,
    verify_csrf,
)
from routes.admin_ui import render_admin_dashboard

# Shared state injected from server.py at import time.
# server.py calls: routes.admin.inject_state(_stats, _stats_lock, _backend_enabled)
_stats: dict = {}
_stats_lock: threading.Lock = threading.Lock()
_backend_enabled: dict = {}
FALLBACK_LOG = "D:/GIT/data/fallback_log.jsonl"


def inject_state(stats: dict, stats_lock: threading.Lock, backend_enabled: dict) -> None:
    """Called once from server.py to wire in shared mutable state."""
    global _stats, _stats_lock, _backend_enabled
    _stats = stats
    _stats_lock = stats_lock
    _backend_enabled = backend_enabled


router = APIRouter(prefix="/admin")


# ── Stats / Logs ───────────────────────────────────────────────────────────────

@router.get("/api/stats", dependencies=[Depends(verify_admin)])
async def admin_stats():
    """返回实时统计数据。"""
    with _stats_lock:
        uptime = int(time.time() - _stats["start_time"])
        total = _stats["total_requests"]
        backend_calls = dict(_stats["backend_calls"])
        avg_ms = 0
        if total > 0:
            total_ms_all = sum(b["total_ms"] for b in backend_calls.values())
            avg_ms = int(total_ms_all / total)
        # 统计不同 IP 和 IDE
        ips = set()
        ide_dist = {}
        for log in _stats["recent_logs"]:
            if log.get("ip"):
                ips.add(log["ip"])
            ide = log.get("ide", "未知")
            ide_dist[ide] = ide_dist.get(ide, 0) + 1
        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(_stats["intent_distribution"]),
            "unique_ips": len(ips),
            "ide_distribution": ide_dist,
        }


@router.get("/api/logs", dependencies=[Depends(verify_admin)])
async def admin_logs():
    """返回最近请求日志。"""
    with _stats_lock:
        return list(reversed(_stats["recent_logs"][-10:]))


@router.get("/api/retrieval-traces", dependencies=[Depends(verify_admin)])
async def admin_retrieval_traces():
    """返回最近的 retrieval injection 追踪记录。"""
    try:
        from context_pipeline.retrieval_trace import get_recent_traces
        return get_recent_traces(limit=20)
    except ImportError:
        return []


# ── Backends ───────────────────────────────────────────────────────────────────

@router.get("/api/backends", dependencies=[Depends(verify_admin)])
async def admin_backends():
    """返回后端列表和状态。"""
    cb = smart_router.cb_status()
    backends = []
    for name, cfg in smart_router.BACKENDS.items():
        enabled = _backend_enabled.get(name, True)
        status_info = cb.get(name, {})
        url = cfg.get("url", "")
        fmt = cfg.get("fmt", "openai")
        auth = cfg.get("auth", "x-api-key" if fmt == "anthropic" else "bearer")
        # 自动检测供应商
        vendor = "未知"
        if "longcat" in url: vendor = "LongCat"
        elif "nvidia" in url: vendor = "英伟达 NVIDIA"
        elif "openrouter" in url: vendor = "OpenRouter"
        elif "deepseek" in url: vendor = "DeepSeek"
        elif "chinamobile" in url: vendor = "中国移动"
        elif "right.codes" in url: vendor = "Claude"
        elif "localhost" in url or "127.0.0.1" in url: vendor = "本地模型"
        # 自动检测层级（用户设置的优先）
        tier = cfg.get("tier", "")
        if not tier:
            if "localhost" in url or "127.0.0.1" in url: tier = "L0 本地"
            elif "longcat" in url or "chinamobile" in url: tier = "L1 免费无限"
            elif "nvidia" in url: tier = "L2 免费额度"
            elif "openrouter" in url: tier = "L3 免费限量"
            elif "deepseek" in url: tier = "L4 付费"
            elif "right.codes" in url: tier = "L4 付费"
            else: tier = "L4 付费"
        # 自动检测协议
        protocol = "Anthropic" if fmt == "anthropic" else "OpenAI"
        # 自动检测能力（用户设置的优先）
        caps = cfg.get("caps", [])
        if not caps:
            if name in ("claude", "or_deepseek_r1", "or_qwen3_coder", "deepseek_pro", "deepseek_flash"):
                caps.append("工具调用")
            if name in ("claude", "longcat_omni"):
                caps.append("视觉")
            if "thinking" in name or "r1" in name:
                caps.append("深度推理")
            if not caps:
                caps.append("纯文本")
        backends.append({
            "name": name,
            "vendor": vendor,
            "tier": tier,
            "protocol": protocol,
            "capabilities": caps,
            "url": url,
            "model": cfg.get("model", ""),
            "auth": auth,
            "enabled": enabled,
            "state": status_info.get("state", "closed"),
            "total_calls": status_info.get("total_calls", 0),
            "error_rate": status_info.get("error_rate", "0.0%"),
        })
    return backends


def _test_backend_sync(name: str) -> dict:
    """同步测试后端连通性，返回结果字典。"""
    if name not in smart_router.BACKENDS:
        return {"ok": False, "error": f"backend '{name}' not found"}
    cfg = smart_router.BACKENDS[name]
    url = cfg.get("url", "")
    key = cfg.get("key", "")
    fmt = cfg.get("fmt", "openai")
    model = cfg.get("model", "")
    start = time.time()
    try:
        if fmt == "anthropic":
            headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}
            if cfg.get("auth") == "bearer":
                headers["Authorization"] = f"Bearer {key}"
            else:
                headers["x-api-key"] = key
            payload = json.dumps({"model": model, "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}).encode()
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
            payload = json.dumps({"model": model, "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}).encode()
        req = __import__('urllib').request.Request(url, data=payload, headers=headers, method='POST')
        resp = __import__('urllib').request.urlopen(req, timeout=15)
        elapsed = int((time.time() - start) * 1000)
        data = json.loads(resp.read().decode())
        caps = ["纯文本"]
        if fmt == "openai" and "tool_calls" not in str(data):
            pass
        return {"ok": True, "latency_ms": elapsed, "status": resp.status, "capabilities_detected": caps, "response_preview": str(data)[:200]}
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return {"ok": False, "latency_ms": elapsed, "error": str(e)[:200]}


@router.post("/api/backends", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_add_backend(req: Request):
    """添加新后端。"""
    body = await req.json()
    name = body.get("name", "").strip()
    url = body.get("url", "").strip()
    key = body.get("key", "").strip()
    model = body.get("model", name)
    fmt = body.get("fmt", "openai")
    auth = body.get("auth", "").strip()
    if not auth:
        auth = "x-api-key" if fmt == "anthropic" else "bearer"
    tier = body.get("tier", "")
    caps = body.get("caps", [])
    if not name or not url:
        raise HTTPException(400, "name and url required")
    if name in smart_router.BACKENDS:
        raise HTTPException(409, f"backend '{name}' already exists")
    smart_router.BACKENDS[name] = {
        "url": url, "key": key, "model": model, "fmt": fmt, "auth": auth,
        "tier": tier, "caps": caps
    }
    _backend_enabled[name] = True
    # 尝试自动测试
    try:
        test_result = _test_backend_sync(name)
        return {"ok": True, "message": f"backend '{name}' added", "test": test_result}
    except Exception as e:
        _backend_enabled[name] = False
        return {"ok": True, "message": f"backend '{name}' added but DISABLED (test failed: {e})", "enabled": False}


@router.delete("/api/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_delete_backend(name: str):
    """删除后端。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    del smart_router.BACKENDS[name]
    _backend_enabled.pop(name, None)
    return {"ok": True, "message": f"backend '{name}' deleted"}


@router.post("/api/backends/{name}/toggle", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_toggle_backend(name: str):
    """启用/禁用后端。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    current = _backend_enabled.get(name, True)
    _backend_enabled[name] = not current
    return {"ok": True, "enabled": not current}


@router.post("/api/backends/{name}/test", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_test_backend(name: str):
    """测试后端可用性：发送简单请求验证连通性。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    return _test_backend_sync(name)


# ── Model status / retrain ─────────────────────────────────────────────────────

@router.get("/api/model-status", dependencies=[Depends(verify_admin)])
async def admin_model_status():
    """返回模型和自动训练状态。"""
    fallback_log = FALLBACK_LOG
    log_count = 0
    recent_logs = []
    if os.path.exists(fallback_log):
        with open(fallback_log, encoding='utf-8') as _f:
            lines = _f.readlines()
        log_count = len(lines)
        for line in lines[-50:]:
            try:
                recent_logs.append(json.loads(line.strip()))
            except Exception:
                pass
    return {
        "model": "Round 12 (Qwen3-1.7B)",
        "accuracy": "89.7%",
        "data_count": 3190,
        "fallback_log_count": log_count,
        "threshold": 100,
        "recent_fallbacks": recent_logs,
    }


@router.post("/api/retrain", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_trigger_retrain():
    """手动触发自动训练。"""
    result = subprocess.run(
        [sys.executable, "auto_retrain.py", "--force"],
        capture_output=True, text=True, cwd="D:/GIT"
    )
    return {"status": "triggered", "output": result.stdout[-500:] if result.stdout else result.stderr[-500:]}


@router.get("", response_class=HTMLResponse)
async def admin_page(
    lima_admin_session: str = Cookie(default=""),
):
    """管理后台 Web UI。仅支持 HttpOnly session cookie 访问。"""
    if not get_admin_token():
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    authenticated = is_valid_admin_session(lima_admin_session)
    if not authenticated:
        return HTMLResponse(
            "<h2>Admin Login</h2>"
            '<form method="post" action="/admin/login">'
            '<input name="token" placeholder="Admin Token" type="password">'
            '<button type="submit">Login</button></form>',
            status_code=401,
        )
    return HTMLResponse(render_admin_dashboard())


@router.post("/login")
async def admin_login(request: Request):
    """POST 登录，设置 httponly cookie。"""
    form = await request.form()
    token = form.get("token", "")
    token_expected = get_admin_token()
    if token != token_expected:
        return HTMLResponse(
            "<h2>Admin Login</h2><p style='color:red'>Token 错误</p>"
            '<form method="post" action="/admin/login">'
            '<input name="token" placeholder="Admin Token" type="password">'
            '<button type="submit">Login</button></form>',
            status_code=401,
        )
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        admin_session_value(),
        httponly=True, secure=True, samesite="strict", max_age=86400,
    )
    return response


@router.get("/logout")
async def admin_logout():
    """清除 cookie 并跳转登录页。"""
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie(SESSION_COOKIE, secure=True, samesite="strict")
    return response
