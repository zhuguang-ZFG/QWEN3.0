"""Admin dashboard HTML rendering."""
from __future__ import annotations

from routes.admin_ui import panels, templates


def render_admin_login(error_msg: str = "") -> str:
    """Return the admin login page HTML."""
    err = f'<p style="color:#f87171;margin:12px 0">{error_msg}</p>' if error_msg else ""
    return f"""\
<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LiMa · 管理登录</title>
<link rel="stylesheet" href="/chat/admin.css?v=20260609">
</head>
<body style="display:grid;place-items:center;min-height:100vh">
<div style="max-width:360px;width:100%;padding:40px">
  <div class="brand" style="justify-content:center;margin-bottom:36px">
    <div class="logo">Li</div>
    <div><h1 style="font-size:22px">LiMa</h1><p style="color:var(--muted);font-size:13px">管理后台登录</p></div>
  </div>
  <form method="post" action="/admin/login" style="display:grid;gap:16px">
    <input name="token" placeholder="Admin Token" type="password"
           style="border:1px solid var(--line);border-radius:12px;background:rgba(8,12,20,0.6);color:var(--text);padding:14px 16px;font-size:14px">
    <button type="submit" class="btn" style="padding:14px;font-size:15px">登 录</button>
  </form>
  {err}
</div>
</body></html>"""


def render_admin_dashboard() -> str:
    """Return authenticated admin dashboard HTML."""
    return (
        templates.HEAD
        + templates.SIDEBAR
        + templates.TOPBAR
        + panels.OVERVIEW
        + panels.TRAFFIC
        + panels.BACKENDS
        + panels.RETRIEVAL
        + panels.MODEL
        + panels.HEALTH
        + panels.CLIENT_KEYS
        + panels.KEYS
        + panels.AGENTS
        + panels.AGENT_TASKS
        + panels.CONFIG
        + panels.DEVICES
        + panels.ALERTS
        + panels.LIVE_LOGS
        + templates.CLOSE
    )
