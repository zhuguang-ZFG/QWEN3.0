"""Backend health dashboard — real-time monitoring endpoint."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()


def _require_admin(request: Request):
    from access_guard import require_private_api_key
    auth = request.headers.get("authorization", "")
    require_private_api_key(authorization=auth)


@router.get("/admin/api/backend-health")
async def backend_health_api(request: Request):
    """JSON API: real-time backend health data for all backends."""
    _require_admin(request)
    return JSONResponse(_collect_backend_health())


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def health_dashboard(request: Request):
    """HTML dashboard: real-time backend health visualization."""
    _require_admin(request)
    data = _collect_backend_health()
    html = _render_dashboard(data)
    return HTMLResponse(html)


def _collect_backend_health() -> dict:
    """Collect comprehensive health data for all backends."""
    import health_tracker
    import budget_manager
    from backends_registry import BACKENDS
    from backends import detect_caps

    scores = health_tracker.get_scores()
    latency_map = health_tracker.get_latency_map()
    health_map = health_tracker.get_health_map()

    backends = []
    for name, cfg in sorted(BACKENDS.items()):
        state = health_tracker.get_backend_state(name)
        caps = detect_caps(name, cfg)
        budget_status = budget_manager.get_budget_status(name)

        backends.append({
            "name": name,
            "health": health_map.get(name, "unknown"),
            "score": scores.get(name, 50),
            "avg_latency_ms": latency_map.get(name, 0),
            "consecutive_failures": state.get("consecutive_failures", 0),
            "cooldown_remaining_s": state.get("cooldown_remaining_s", 0),
            "last_error_code": state.get("last_error_code"),
            "last_error_class": state.get("last_error_class"),
            "total_requests": state.get("total_requests", 0),
            "empty_count": state.get("empty_count", 0),
            "caps": caps,
            "budget": budget_status,
            "model": cfg.get("model", ""),
        })

    healthy = sum(1 for b in backends if b["health"] == "healthy")
    degraded = sum(1 for b in backends if b["health"] == "degraded")
    dead = sum(1 for b in backends if b["health"] == "dead")
    unknown = sum(1 for b in backends if b["health"] == "unknown")
    cooled = sum(1 for b in backends if b["cooldown_remaining_s"] > 0)

    return {
        "timestamp": time.time(),
        "total": len(backends),
        "healthy": healthy,
        "degraded": degraded,
        "dead": dead,
        "unknown": unknown,
        "probed": len(backends) - unknown,
        "cooled": cooled,
        "backends": backends,
    }


def _render_dashboard(data: dict) -> str:
    """Render HTML dashboard from health data."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data["timestamp"]))
    rows = []
    for b in sorted(data["backends"], key=lambda x: -x["score"]):
        health = b["health"]
        if health == "healthy":
            color = "#22c55e"
            badge = "Healthy"
        elif health == "degraded":
            color = "#eab308"
            badge = "Degraded"
        elif health == "dead":
            color = "#ef4444"
            badge = "Dead"
        else:
            color = "#6b7280"
            badge = "Unknown"

        cooldown = ""
        if b["cooldown_remaining_s"] > 0:
            cooldown = f"{b['cooldown_remaining_s']:.0f}s"

        error_info = ""
        if b["last_error_code"]:
            error_info = f"HTTP {b['last_error_code']}"
        elif b["last_error_class"]:
            error_info = b["last_error_class"]

        caps_str = ", ".join(b["caps"]) if b["caps"] else "-"

        rows.append(f"""
        <tr>
            <td><span style="color:{color};font-weight:bold">●</span> {b['name']}</td>
            <td>{badge}</td>
            <td>{b['score']:.0f}</td>
            <td>{b['avg_latency_ms']:.0f}ms</td>
            <td>{b['total_requests']}</td>
            <td>{cooldown or '-'}</td>
            <td>{error_info or '-'}</td>
            <td>{caps_str}</td>
            <td>{b['budget']}</td>
        </tr>""")

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>LiMa Backend Health Dashboard</title>
<meta http-equiv="refresh" content="30">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f8fafc; }}
h1 {{ color: #1e293b; }}
.stats {{ display: flex; gap: 20px; margin: 20px 0; }}
.stat {{ background: white; padding: 15px 25px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
.stat .num {{ font-size: 2em; font-weight: bold; }}
.stat .label {{ color: #64748b; font-size: 0.9em; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #1e293b; color: white; padding: 12px 15px; text-align: left; font-size: 0.85em; }}
td {{ padding: 10px 15px; border-bottom: 1px solid #e2e8f0; font-size: 0.9em; }}
tr:hover {{ background: #f1f5f9; }}
.timestamp {{ color: #94a3b8; font-size: 0.85em; margin-top: 20px; }}
</style>
</head><body>
<h1>LiMa Backend Health Dashboard</h1>
<div class="stats">
    <div class="stat"><div class="num" style="color:#22c55e">{data['healthy']}</div><div class="label">Healthy</div></div>
    <div class="stat"><div class="num" style="color:#eab308">{data['degraded']}</div><div class="label">Degraded</div></div>
    <div class="stat"><div class="num" style="color:#ef4444">{data['dead']}</div><div class="label">Dead</div></div>
    <div class="stat"><div class="num" style="color:#6b7280">{data['cooled']}</div><div class="label">Cooled Down</div></div>
    <div class="stat"><div class="num">{data['total']}</div><div class="label">Total Backends</div></div>
</div>
<table>
<tr><th>Backend</th><th>Status</th><th>Score</th><th>Latency</th><th>Requests</th><th>Cooldown</th><th>Last Error</th><th>Capabilities</th><th>Budget</th></tr>
{''.join(rows)}
</table>
<div class="timestamp">Last updated: {ts} | Auto-refresh: 30s</div>
</body></html>"""
