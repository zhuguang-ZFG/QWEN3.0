"""Admin UI base templates — HEAD, SIDEBAR, TOPBAR, CLOSE."""

HEAD = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LiMa · 管理后台</title>
<link rel="stylesheet" href="/chat/admin.css?v=20260609">
</head>"""

SIDEBAR = """\
<body>
<div class="sidebar-overlay"></div>
<button class="mobile-menu-toggle" onclick="toggleMobileMenu()"><span></span></button>
<div class="shell">
<aside class="sidebar">
  <div class="brand">
    <div class="logo">Li</div>
    <div><h1>LiMa</h1><p>智能路由管理后台</p></div>
  </div>
  <nav class="nav" id="nav">
    <button class="active" data-panel="overview">📊 概览</button>
    <button data-panel="traffic">📋 请求日志</button>
    <button data-panel="backends">🔌 后端管理</button>
    <button data-panel="retrieval">🔍 检索追踪</button>
    <button data-panel="model">🧠 路由模型</button>
    <button data-panel="health">💊 健康监控</button>
    <button data-panel="client-keys">🔑 客户端 Key</button>
    <button data-panel="keys">🔐 Key-URL 清单</button>
    <button data-panel="agents">🤖 Agent 审计</button>
    <button data-panel="agent-tasks">📝 Agent 任务</button>
    <button data-panel="config">⚙️ 配置管理</button>
    <button data-panel="devices">📱 设备管理</button>
    <button data-panel="alerts">🔔 告警规则</button>
    <button data-panel="live-logs">📡 实时日志</button>
  </nav>
  <div class="sidebar-footer">
    <div class="status-dot">系统运行中</div>
    <div style="margin-top:8px"><a href="/admin/logout" style="color:var(--muted)">退出登录</a></div>
  </div>
</aside>
<main class="main">
"""

TOPBAR = """\
<div class="topbar">
  <div>
    <div class="eyebrow">ADMIN CONSOLE</div>
    <h1 class="title">LiMa 管理后台</h1>
    <p class="subtitle">实时监控、后端管理、路由模型、Agent 任务全生命周期管控</p>
  </div>
  <div class="toolbar">
    <button class="btn ghost" onclick="refreshAll()">⟳ 刷新</button>
    <span class="mini" id="refresh-info">每10秒自动刷新</span>
  </div>
</div>
"""

CLOSE = """\
</main>
</div>
<div class="toast" id="toast"></div>
<script src="/chat/admin.js?v=20260609"></script>
</body>
</html>"""
