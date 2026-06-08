"""Admin dashboard HTML/JS templates (LiMa)."""

ADMIN_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LIMA 管理面板</title>
<style>
:root{color-scheme:dark;--bg:#0a0f1a;--bg2:#0f1629;--panel:rgba(15,23,42,0.85);--panel2:rgba(20,30,55,0.92);--line:rgba(100,130,180,0.2);--text:#e2e8f0;--muted:#94a3b8;--cyan:#06b6d4;--blue:#3b82f6;--green:#10b981;--amber:#f59e0b;--red:#ef4444;--violet:#8b5cf6;--shadow:0 20px 60px rgba(0,0,0,0.4)}
*{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}body{min-height:100vh;background:radial-gradient(circle at 15% 0%,rgba(6,182,212,0.15),transparent 30%),radial-gradient(circle at 85% 10%,rgba(139,92,246,0.15),transparent 35%),linear-gradient(145deg,#080c14 0%,#0a0f1a 50%,#0f1420 100%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.6}
.shell{display:grid;grid-template-columns:280px 1fr;min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;padding:28px 20px;border-right:1px solid var(--line);background:linear-gradient(180deg,rgba(10,15,26,0.96),rgba(10,15,26,0.75));backdrop-filter:blur(20px)}
.brand{display:flex;gap:14px;align-items:center;margin-bottom:28px}
.logo{width:48px;height:48px;border-radius:18px;background:linear-gradient(135deg,var(--cyan),var(--violet));box-shadow:0 0 35px rgba(6,182,212,0.35);display:grid;place-items:center;font-size:22px;font-weight:900;color:#fff}
.brand h1{font-size:20px;font-weight:800;letter-spacing:-0.02em}
.brand p{margin-top:4px;color:var(--muted);font-size:12px}
.nav{display:grid;gap:10px}
.nav button{width:100%;text-align:left;border:1px solid transparent;border-radius:14px;background:transparent;color:var(--muted);padding:12px 14px;cursor:pointer;font-size:14px;font-weight:500;transition:all 0.2s}
.nav button:hover{color:var(--text);background:rgba(59,130,246,0.1);border-color:rgba(59,130,246,0.2)}
.nav button.active{color:var(--cyan);background:rgba(6,182,212,0.12);border-color:rgba(6,182,212,0.3);font-weight:700}
.sidebar-footer{position:absolute;bottom:24px;left:20px;right:20px;color:var(--muted);font-size:12px}
.status-dot{display:inline-flex;align-items:center;gap:8px}
.status-dot:before{content:"";width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 12px var(--green)}
.main{padding:32px;min-width:0}
.topbar{display:flex;gap:18px;align-items:flex-start;justify-content:space-between;margin-bottom:26px}
.eyebrow{color:var(--cyan);font-weight:800;letter-spacing:0.14em;text-transform:uppercase;font-size:11px}
.title{font-size:36px;font-weight:900;letter-spacing:-0.04em;margin:8px 0 10px;background:linear-gradient(135deg,var(--cyan),var(--violet));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{color:var(--muted);margin:0;max-width:800px;line-height:1.7}
.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.btn{border:1px solid rgba(6,182,212,0.3);border-radius:12px;background:rgba(6,182,212,0.12);color:var(--text);padding:10px 14px;cursor:pointer;font-weight:700;font-size:13px;transition:all 0.2s}
.btn:hover{border-color:var(--cyan);box-shadow:0 0 0 4px rgba(6,182,212,0.12);transform:translateY(-1px)}
.btn.danger{border-color:rgba(239,68,68,0.4);background:rgba(239,68,68,0.15)}
.btn.ghost{background:rgba(148,163,184,0.08);border-color:var(--line);color:var(--muted)}
.btn.ghost:hover{border-color:var(--muted);color:var(--text)}
.section{display:none}.section.active{display:block;animation:fadeIn 0.3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.bento{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.card{grid-column:span 4;background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:24px;padding:20px;box-shadow:var(--shadow);min-width:0;transition:transform 0.2s,box-shadow 0.2s}
.card:hover{transform:translateY(-2px);box-shadow:0 24px 70px rgba(0,0,0,0.45)}
.card.wide{grid-column:span 8}.card.full{grid-column:1/-1}
.card h2{font-size:16px;font-weight:700;margin:0 0 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.metric{font-size:38px;font-weight:900;letter-spacing:-0.05em}
.metric-label{color:var(--muted);font-size:12px;margin-top:6px;font-weight:500}
.mini{color:var(--muted);font-size:12px}
.table-wrap{overflow:auto;max-height:560px;border-radius:16px;border:1px solid rgba(100,130,180,0.15)}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:900px}
th,td{padding:12px 14px;text-align:left;border-bottom:1px solid rgba(100,130,180,0.12);vertical-align:middle}
th{position:sticky;top:0;background:#0f172a;color:#cbd5e1;font-size:11px;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;z-index:1}
tr:hover td{background:rgba(59,130,246,0.08)}
.badge{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px;font-size:11px;font-weight:800;border:1px solid transparent;white-space:nowrap}
.badge-ok{background:rgba(16,185,129,0.15);color:#34d399;border-color:rgba(16,185,129,0.3)}
.badge-warn{background:rgba(245,158,11,0.15);color:#fbbf24;border-color:rgba(245,158,11,0.3)}
.badge-err{background:rgba(239,68,68,0.15);color:#f87171;border-color:rgba(239,68,68,0.35)}
.badge-off{background:rgba(148,163,184,0.12);color:#cbd5e1;border-color:rgba(148,163,184,0.2)}
.badge-info{background:rgba(59,130,246,0.15);color:#60a5fa;border-color:rgba(59,130,246,0.3)}
.mono{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;font-size:12px}
.truncate{max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.form{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.form input,.form select,.search{width:100%;border:1px solid var(--line);border-radius:12px;background:rgba(8,12,20,0.6);color:var(--text);padding:11px 12px;font-size:13px;transition:border-color 0.2s}
.form input:focus,.form select:focus,.search:focus{outline:none;border-color:var(--cyan);box-shadow:0 0 0 4px rgba(6,182,212,0.1)}
.form .span2{grid-column:span 2}.form .span3{grid-column:span 3}
.toast{position:fixed;right:24px;bottom:24px;max-width:480px;background:#0f172a;border:1px solid var(--line);border-radius:16px;padding:14px 16px;box-shadow:var(--shadow);display:none;z-index:1000}
.toast.show{display:block;animation:slideIn 0.3s}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
.empty{padding:32px;color:var(--muted);text-align:center}
.spark{height:8px;border-radius:999px;background:rgba(148,163,184,0.15);overflow:hidden}
.spark span{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),var(--violet));width:0;transition:width 0.5s}
.filter-bar{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.filter-bar button{padding:8px 12px;font-size:12px}
.filter-bar button.active{border-color:var(--cyan);color:var(--cyan)}
@media(max-width:1024px){.shell{grid-template-columns:1fr}.sidebar{position:relative;height:auto;padding:20px}.sidebar-footer{position:static;margin-top:20px}.main{padding:20px}.card,.card.wide{grid-column:1/-1}.topbar{display:block}.toolbar{margin-top:16px}.form{grid-template-columns:1fr 1fr}.form .span2,.form .span3{grid-column:auto}}
@media(max-width:768px){.main{padding:16px}.card,.card.wide{padding:14px;border-radius:16px}.toolbar{flex-direction:column;align-items:stretch}.toolbar .btn,.filter-bar button{padding:12px 14px;min-height:44px;font-size:13px}.form{grid-template-columns:1fr}.form .span2,.form .span3{grid-column:auto}.bento{gap:12px}.title{font-size:24px}.notification{left:16px;right:16px;max-width:none;top:60px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:0.01ms!important;animation-iteration-count:1!important;transition-duration:0.01ms!important}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
<div class="brand"><div class="logo">L</div><div><h1>LIMA 管理面板</h1><p>AI 路由运维中心</p></div></div>
<nav class="nav" id="nav">
<button class="active" data-panel="overview">总览</button>
<button data-panel="traffic">流量日志</button>
<button data-panel="backends">后端管理</button>
<button data-panel="retrieval">检索追踪</button>
<button data-panel="model">模型与训练</button>
<button data-panel="health">健康状态</button>
<button data-panel="client-keys">客户端 Key</button>
<button data-panel="keys">密钥与端点</button>
<button data-panel="agents">Agent 审计</button>
<button data-panel="agent-tasks">Agent 任务</button>
<button data-panel="live-logs">实时日志</button>
<button data-panel="config">配置管理</button>
<button data-panel="devices">设备管理</button>
<button data-panel="alerts">告警配置</button>
</nav>
<div class="sidebar-footer"><div class="status-dot">管理会话已启用</div><div style="margin-top:10px"><a href="/admin/logout" style="color:var(--muted);text-decoration:none">退出登录</a></div></div>
</aside>
<main class="main">
<header class="topbar">
<div><div class="eyebrow">生产控制台</div><h1 class="title">LIMA 管理面板</h1><p class="subtitle">统一查看路由健康、请求流量、后端能力、检索链路、模型 fallback 与 Agent 任务审计。</p></div>
<div class="toolbar"><span class="status-dot" id="refresh-info">等待刷新</span><button class="btn" onclick="refreshAll()">立即刷新</button></div>
</header>

<section id="panel-overview" class="section active">
<div class="bento">
<div class="card"><h2>请求总量</h2><div class="metric" id="s-total">0</div><div class="metric-label">Total requests</div></div>
<div class="card"><h2>平均延迟</h2><div class="metric" id="s-avg-ms">0ms</div><div class="metric-label">Average latency</div></div>
<div class="card"><h2>运行时间</h2><div class="metric" id="s-uptime">0s</div><div class="metric-label">Service uptime</div></div>
<div class="card"><h2>后端数</h2><div class="metric" id="s-backends">0</div><div class="metric-label">Configured backends</div></div>
<div class="card"><h2>独立 IP</h2><div class="metric" id="s-ips">0</div><div class="metric-label">Unique clients</div></div>
<div class="card"><h2>Fallback</h2><div class="metric" id="s-fallbacks">0</div><div class="metric-label">Fallback log entries</div></div>
<div class="card full" style="display:flex;gap:24px;align-items:center;flex-wrap:wrap"><h2 style="margin:0">版本信息</h2><div style="display:flex;gap:16px;flex-wrap:wrap"><div><span class="metric-label">Git Commit</span> <span class="mono" id="s-git" style="color:var(--cyan)">-</span></div><div><span class="metric-label">Python</span> <span class="mono" id="s-py" style="color:var(--cyan)">-</span></div><div><span class="metric-label">服务器时间</span> <span class="mono" id="s-time" style="color:var(--muted)">-</span></div></div></div>
<div class="card wide"><h2>后端调用排行 <span class="mini">成功率 / 平均耗时</span></h2><div class="table-wrap"><table><thead><tr><th>后端</th><th>调用</th><th>成功率</th><th>平均 ms</th><th>热度</th></tr></thead><tbody id="t-backends"></tbody></table></div></div>
<div class="card"><h2>意图分布</h2><div class="table-wrap"><table><thead><tr><th>意图</th><th>数量</th><th>占比</th></tr></thead><tbody id="t-intents"></tbody></table></div></div>
<div class="card full"><h2>IDE / 入口分布</h2><div id="ide-bars"></div></div>
</div>
</section>

<section id="panel-traffic" class="section"><div class="bento"><div class="card full"><h2>最近请求 <input class="search" id="log-filter" placeholder="搜索 IP / query / backend / intent" oninput="renderLogs()"> <button class="btn ghost" onclick="exportLogsCSV()" style="font-size:11px">导出 CSV</button> <button class="btn ghost" onclick="exportLogsJSON()" style="font-size:11px">导出 JSON</button></h2><div class="table-wrap"><table><thead><tr><th>时间</th><th>IP</th><th>地区</th><th>IDE</th><th>Query</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead><tbody id="t-logs"></tbody></table></div></div></div></section>

<section id="panel-backends" class="section"><div class="bento">
<div class="card full"><h2>添加后端</h2><div class="form"><input id="be-name" placeholder="name" class="span2"><input id="be-url" placeholder="url" class="span3"><input id="be-model" placeholder="model"><input id="be-key" placeholder="API Key (不会回显)" type="password" class="span2"><select id="be-fmt"><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select><select id="be-auth"><option value="bearer">Bearer</option><option value="x-api-key">x-api-key</option></select><input id="be-tier" placeholder="tier"><select id="be-admission" class="span2"><option value="">默认 (IDE/Chat)</option><option value="code_medium_candidate">编程池 (code_medium)</option><option value="sandbox_only">仅沙箱</option></select><button class="btn" onclick="addBackend()">添加并测试</button></div></div>
<div class="card full"><h2>后端库存 <input class="search" id="backend-filter" placeholder="搜索 name / model / url / capability" oninput="renderBackends()"></h2>
<div class="filter-bar">
<button class="btn ghost active" onclick="filterPool('all')" id="pool-all">全部</button>
<button class="btn ghost" onclick="filterPool('ide')" id="pool-ide">IDE 池</button>
<button class="btn ghost" onclick="filterPool('chat')" id="pool-chat">Chat 池</button>
<button class="btn ghost" onclick="filterPool('code')" id="pool-code">编程池</button>
<button class="btn ghost" onclick="filterPool('sandbox')" id="pool-sandbox">沙箱</button>
</div>
<div id="batch-bar" style="display:none;margin-bottom:10px;padding:10px 14px;border:1px solid var(--cyan);border-radius:12px;background:rgba(6,182,212,0.08)"><span id="batch-count" style="color:var(--cyan);font-weight:700"></span> <button class="btn ghost" onclick="batchTest()">批量测试</button> <button class="btn danger" onclick="batchDisable()">批量禁用</button> <button class="btn ghost" onclick="batchEnable()">批量启用</button></div>
<div class="table-wrap"><table><thead><tr><th style="width:36px"><input type="checkbox" id="be-select-all" onchange="toggleSelectAll(this)"></th><th>状态</th><th>名称</th><th>URL</th><th>模型</th><th>Key</th><th>格式</th><th>能力</th><th>所属池</th><th>准入</th><th>调用</th><th>错误率</th><th>操作</th></tr></thead><tbody id="t-be-list"></tbody></table></div></div>
</div></section>

<section id="panel-retrieval" class="section"><div class="bento">
<div class="card"><h2>检索追踪</h2><div class="metric" id="r-count">0</div><div class="metric-label">记录数</div></div>
<div class="card"><h2>平均候选</h2><div class="metric" id="r-avg-cand">0</div><div class="metric-label">candidates searched</div></div>
<div class="card"><h2>平均精度</h2><div class="metric" id="r-avg-prec">0%</div><div class="metric-label">retrieval precision</div></div>
<div class="card"><h2>有效注入率</h2><div class="metric" id="r-useful">0%</div><div class="metric-label">injection useful</div></div>
<div class="card full"><h2>检索链路追踪</h2><div class="table-wrap"><table><thead><tr><th>时间</th><th>后端</th><th>Query</th><th>候选</th><th>注入</th><th>精度</th><th>有用</th><th>策略</th></tr></thead><tbody id="t-retrieval"></tbody></table></div></div>
</div></section>

<section id="panel-model" class="section"><div class="bento">
<div class="card"><h2>路由模型</h2><div class="metric" id="m-name">-</div><div class="metric-label">当前模型</div></div>
<div class="card"><h2>准确率</h2><div class="metric" id="m-accuracy">-</div><div class="metric-label">训练评估</div></div>
<div class="card"><h2>训练数据</h2><div class="metric" id="m-data">0</div><div class="metric-label">样本数</div></div>
<div class="card full"><h2>Fallback 根因分析 <span class="mini" id="fb-total">0</span> 条记录</h2><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><div class="card" style="margin:0;background:transparent;border:1px solid var(--line)"><h2 style="font-size:14px">触发后端排行</h2><div class="table-wrap" style="max-height:200px"><table><thead><tr><th>后端</th><th>次数</th><th>占比</th><th></th></tr></thead><tbody id="fb-by-backend"></tbody></table></div></div><div class="card" style="margin:0;background:transparent;border:1px solid var(--line)"><h2 style="font-size:14px">意图分布</h2><div class="table-wrap" style="max-height:200px"><table><thead><tr><th>意图</th><th>次数</th><th>占比</th></tr></thead><tbody id="fb-by-intent"></tbody></table></div></div></div><div style="margin-top:14px"><h3 style="font-size:13px;color:var(--muted);margin-bottom:8px">24h 趋势</h3><div id="fb-hourly" style="height:80px"></div></div></div>
<div class="card full"><h2>Fallback 样本与训练 <button class="btn" onclick="triggerRetrain()">触发重训</button></h2><div id="retrain-progress" style="margin-bottom:12px"></div><div class="table-wrap"><table><thead><tr><th>时间</th><th>Query</th><th>后端</th><th>意图</th></tr></thead><tbody id="t-fallbacks"></tbody></table></div></div>
</div></section>

<section id="panel-health" class="section"><div class="bento">
<div class="card"><h2>健康</h2><div class="metric" id="h-healthy">0</div><div class="metric-label">Healthy</div></div>
<div class="card"><h2>降级</h2><div class="metric" id="h-degraded">0</div><div class="metric-label">Degraded</div></div>
<div class="card"><h2>死亡</h2><div class="metric" id="h-dead">0</div><div class="metric-label">Dead</div></div>
<div class="card"><h2>冷却中</h2><div class="metric" id="h-cooled">0</div><div class="metric-label">Cooled down</div></div>
<div class="card full"><h2>后端健康状态</h2><div class="table-wrap"><table><thead><tr><th>后端</th><th>状态</th><th>评分</th><th>延迟 ms</th><th>CB 状态</th><th>CB 失败</th><th>CB 调用</th><th>连续失败</th><th>冷却剩余</th><th>错误码</th></tr></thead><tbody id="t-health"></tbody></table></div></div>
</div></section>

<section id="panel-client-keys" class="section"><div class="bento">
<div class="card"><h2>Key 总数</h2><div class="metric" id="ck-total">0</div><div class="metric-label">Total keys</div></div>
<div class="card"><h2>已启用</h2><div class="metric" id="ck-enabled">0</div><div class="metric-label">Active keys</div></div>
<div class="card"><h2>已禁用</h2><div class="metric" id="ck-disabled">0</div><div class="metric-label">Disabled keys</div></div>
<div class="card"><h2>今日活跃</h2><div class="metric" id="ck-active-today">0</div><div class="metric-label">Used today</div></div>
<div class="card full"><h2>客户端 Key 管理 <button class="btn" onclick="showCreateKeyForm()">+ 发放新 Key</button></h2>
<div class="table-wrap"><table><thead><tr><th>Key (脱敏)</th><th>标签</th><th>状态</th><th>日限额</th><th>月限额</th><th>已用 (今日)</th><th>已用 (月)</th><th>最后使用</th><th>允许 URL</th><th>操作</th></tr></thead><tbody id="t-client-keys"></tbody></table></div></div>
</div></section>

<section id="panel-keys" class="section"><div class="bento">
<div class="card full"><h2>后端密钥与端点 <input class="search" id="key-filter" placeholder="搜索 name / url / model" oninput="renderKeyUrlTable()"></h2><div class="table-wrap"><table><thead><tr><th>名称</th><th>URL</th><th>Key (脱敏)</th><th>模型</th><th>格式</th><th>操作</th></tr></thead><tbody id="t-key-url"></tbody></table></div></div>
<div class="card full"><h2>Provider Key Pool 状态</h2><div id="key-pool-info"></div></div>
</div></section>

<section id="panel-agents" class="section"><div class="bento"><div class="card full"><h2>Agent Task Audit</h2><div class="table-wrap"><table><thead><tr><th>Task</th><th>Status</th><th>Mode</th><th>Repo</th><th>Goal</th><th>Events</th><th>Next</th></tr></thead><tbody id="t-agent-audit"></tbody></table></div></div></div></section>

<section id="panel-agent-tasks" class="section"><div class="bento">
<div class="card"><h2>任务总数</h2><div class="metric" id="at-total">0</div><div class="metric-label">Total tasks</div></div>
<div class="card"><h2>运行中</h2><div class="metric" id="at-running">0</div><div class="metric-label">Running</div></div>
<div class="card"><h2>已完成</h2><div class="metric" id="at-completed">0</div><div class="metric-label">Completed</div></div>
<div class="card"><h2>失败</h2><div class="metric" id="at-failed">0</div><div class="metric-label">Failed</div></div>
<div class="card full"><h2>Agent 任务管理</h2><div class="filter-bar"><button class="btn ghost active" onclick="filterAgentTasks('')" id="at-all">全部</button><button class="btn ghost" onclick="filterAgentTasks('accepted')" id="at-accepted">待处理</button><button class="btn ghost" onclick="filterAgentTasks('running')" id="at-running-btn">运行中</button><button class="btn ghost" onclick="filterAgentTasks('completed')" id="at-completed-btn">已完成</button><button class="btn ghost" onclick="filterAgentTasks('failed')" id="at-failed-btn">失败</button></div><div class="table-wrap"><table><thead><tr><th>Task ID</th><th>状态</th><th>Worker</th><th>后端</th><th>描述</th><th>创建时间</th><th>操作</th></tr></thead><tbody id="t-agent-tasks"></tbody></table></div></div>
</div></section>

<section id="panel-live-logs" class="section"><div class="bento">
<div class="card"><h2>SSE 连接</h2><div class="metric" id="ll-status">未连接</div><div class="metric-label">Connection status</div></div>
<div class="card"><h2>已接收</h2><div class="metric" id="ll-count">0</div><div class="metric-label">Events received</div></div>
<div class="card"><h2>成功</h2><div class="metric" id="ll-success">0</div><div class="metric-label">Successful requests</div></div>
<div class="card"><h2>失败</h2><div class="metric" id="ll-fail">0</div><div class="metric-label">Failed requests</div></div>
<div class="card full"><h2>实时日志流 <input class="search" id="ll-filter" placeholder="搜索 IP / query / backend / intent" oninput="filterLiveLogs()"> <button class="btn ghost" id="ll-toggle" onclick="toggleLiveLogs()">开始监听</button> <button class="btn ghost" onclick="clearLiveLogs()">清空</button></h2><div style="max-height:500px;overflow-y:auto;border:1px solid var(--line);border-radius:12px"><table><thead><tr><th>时间</th><th>IP</th><th>地区</th><th>IDE</th><th>Query</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead><tbody id="t-live-logs"></tbody></table></div></div>
</div></section>

<section id="panel-config" class="section"><div class="bento">
<div class="card"><h2>导出配置</h2><p style="color:var(--muted);margin:8px 0">导出后端覆盖和准入配置为 JSON 文件，用于备份或迁移。</p><button class="btn" onclick="exportConfig()">导出配置</button></div>
<div class="card"><h2>导入配置</h2><p style="color:var(--muted);margin:8px 0">从 JSON 文件导入配置。会覆盖现有的后端覆盖和准入配置。</p><input type="file" id="config-file" accept=".json" style="margin:8px 0;color:var(--text)"><button class="btn" onclick="importConfig()">导入配置</button></div>
<div class="card"><h2>配置版本</h2><div class="metric" id="cfg-version">-</div><div class="metric-label">Config version</div></div>
<div class="card full"><h2>当前配置预览</h2><div style="max-height:400px;overflow:auto;background:rgba(8,12,20,0.6);border:1px solid var(--line);border-radius:12px;padding:12px"><pre id="cfg-preview" class="mono" style="font-size:12px;color:var(--muted)">加载中...</pre></div></div>
</div></section>

<section id="panel-devices" class="section"><div class="bento">
<div class="card"><h2>在线设备</h2><div class="metric" id="dev-total">0</div><div class="metric-label">Connected devices</div></div>
<div class="card"><h2>MQTT 设备</h2><div class="metric" id="dev-mqtt">0</div><div class="metric-label">MQTT-connected</div></div>
<div class="card"><h2>WebSocket 设备</h2><div class="metric" id="dev-ws">0</div><div class="metric-label">WS-connected</div></div>
<div class="card"><h2>总任务数</h2><div class="metric" id="dev-tasks">0</div><div class="metric-label">Inflight tasks</div></div>
<div class="card full"><h2>设备列表 <button class="btn ghost" onclick="loadDevices()">刷新</button></h2><div class="table-wrap"><table><thead><tr><th>Device ID</th><th>固件版本</th><th>能力</th><th>运行时间</th><th>任务数</th><th>操作</th></tr></thead><tbody id="t-devices"></tbody></table></div></div>
</div></section>

<section id="panel-alerts" class="section"><div class="bento">
<div class="card"><h2>告警规则数</h2><div class="metric" id="alert-total">0</div><div class="metric-label">Total rules</div></div>
<div class="card"><h2>已启用</h2><div class="metric" id="alert-active">0</div><div class="metric-label">Enabled rules</div></div>
<div class="card full"><h2>告警规则 <button class="btn" onclick="showAddAlert()">添加规则</button></h2><div class="table-wrap"><table><thead><tr><th>ID</th><th>名称</th><th>指标</th><th>条件</th><th>阈值</th><th>窗口</th><th>状态</th><th>操作</th></tr></thead><tbody id="t-alerts"></tbody></table></div></div>
<div class="card full" id="alert-add-form" style="display:none"><h2>添加告警规则</h2><div class="form"><input id="al-name" placeholder="规则名称" class="span2"><select id="al-metric" class="span2"><option value="error_rate">错误率</option><option value="latency_ms">延迟 (ms)</option><option value="fallback_rate">Fallback 率</option><option value="request_count">请求量</option></select><select id="al-condition"><option value="gt">大于 (>)</option><option value="lt">小于 (<)</option><option value="eq">等于 (=)</option></select><input id="al-threshold" placeholder="阈值" type="number" value="0.5"><input id="al-window" placeholder="窗口(秒)" type="number" value="300"><button class="btn" onclick="addAlertRule()">保存</button> <button class="btn ghost" onclick="hideAddAlert()">取消</button></div></div>
</div></section>
</main>
</div>
<div class="toast" id="toast"></div>
<script>
var state={stats:null,logs:[],backends:[],model:null,traces:[],agents:[],health:{backends:[],summary:{}},fallbackAnalysis:null,keyUrl:{backends:[],key_pools:{}},_poolFilter:'all',_loading:false};
function authFetch(url,opts){opts=opts||{};opts.headers=Object.assign({'Content-Type':'application/json'},opts.headers||{});opts.credentials='same-origin';return fetch(url,opts)}
function esc(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
function escJs(v){return String(v==null?'':v).replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'").replace(/\\n/g,' ')}
function badge(text,type){type=type||'off';return '<span class="badge badge-'+type+'">'+esc(text)+'</span>'}
function fmtUptime(s){s=Number(s||0);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';var d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60);return(d?d+'d ':'')+h+'h '+m+'m'}
function toast(msg,type){type=type||'ok';var el=document.getElementById('toast');el.textContent=msg;el.style.borderColor=type==='err'?'rgba(239,68,68,0.5)':type==='warn'?'rgba(245,158,11,0.5)':'rgba(6,182,212,0.4)';el.classList.add('show');setTimeout(function(){el.classList.remove('show')},4200)}
function setRefreshStatus(text){document.getElementById('refresh-info').textContent=text}
async function json(url,opts){try{var r=await authFetch(url,opts);if(!r.ok){var errBody='';try{errBody=await r.text()}catch(e){}throw new Error('HTTP '+r.status+': '+(errBody.substring(0,200)||r.statusText))}return r.json()}catch(e){console.error('API error:',url,e.message);throw e}}
async function refreshAll(){try{setRefreshStatus('刷新中...');await Promise.allSettled([loadStats(),loadLogs(),loadBackends(),loadModel(),loadFallbackAnalysis(),loadRetrieval(),loadAgents(),loadHealth(),loadKeyUrl(),loadAgentTasks(),loadConfig(),loadDevices(),loadAlerts()]);setRefreshStatus('已刷新 '+new Date().toLocaleTimeString())}catch(e){setRefreshStatus('刷新失败: '+e.message);console.error('refreshAll error:',e)}}
async function loadStats(){try{state.stats=await json('/admin/api/stats');renderStats()}catch(e){console.error('loadStats failed:',e)}}
function renderStats(){var d=state.stats||{};document.getElementById('s-total').textContent=d.total_requests||0;document.getElementById('s-avg-ms').textContent=(d.avg_response_ms||0)+'ms';document.getElementById('s-uptime').textContent=fmtUptime(d.uptime_seconds);document.getElementById('s-ips').textContent=d.unique_ips||0;var calls=d.backend_calls||{};document.getElementById('s-backends').textContent=Object.keys(calls).length;var tbody=document.getElementById('t-backends');tbody.innerHTML='';var max=Math.max(1,Math.max.apply(null,Object.keys(calls).map(function(k){return Number(calls[k].count||0)})));Object.keys(calls).sort(function(a,b){return(calls[b].count||0)-(calls[a].count||0)}).slice(0,12).forEach(function(name){var info=calls[name];var count=Number(info.count||0),success=Number(info.success||0),rate=count?Math.round(success/count*100):0,avg=count?Math.round(Number(info.total_ms||0)/count):0;tbody.innerHTML+='<tr><td class="mono">'+esc(name)+'</td><td>'+count+'</td><td>'+badge(rate+'%',rate>90?'ok':rate>60?'warn':'err')+'</td><td>'+avg+'</td><td><div class="spark"><span style="width:'+Math.round(count/max*100)+'%"></span></div></td></tr>'});renderIntentTable(d.intent_distribution||{});renderIdeBars(d.ide_distribution||{});var v=d.version||{};document.getElementById('s-git').textContent=v.git_commit||'unknown';document.getElementById('s-py').textContent=v.python_version||'-';document.getElementById('s-time').textContent=new Date().toLocaleString()}
function renderIntentTable(map){var rows=Object.keys(map).map(function(k){return[k,map[k]]}).sort(function(a,b){return b[1]-a[1]});var total=rows.reduce(function(a,b){return a+Number(b[1]||0)},0)||1;document.getElementById('t-intents').innerHTML=rows.map(function(pair){return '<tr><td>'+esc(pair[0])+'</td><td>'+pair[1]+'</td><td>'+Math.round(Number(pair[1])/total*100)+'%</td></tr>'}).join('')||'<tr><td colspan="3" class="empty">暂无数据</td></tr>'}
function renderIdeBars(map){var rows=Object.keys(map).map(function(k){return[k,map[k]]}).sort(function(a,b){return b[1]-a[1]});var max=Math.max.apply(null,[1].concat(rows.map(function(r){return Number(r[1]||0)})));document.getElementById('ide-bars').innerHTML=rows.map(function(pair){return '<div style="display:grid;grid-template-columns:160px 1fr 50px;gap:10px;align-items:center;margin:10px 0"><span>'+esc(pair[0])+'</span><div class="spark"><span style="width:'+Math.round(Number(pair[1])/max*100)+'%"></span></div><span class="mono">'+pair[1]+'</span></div>'}).join('')||'<div class="empty">暂无数据</div>'}
async function loadLogs(){try{state.logs=await json('/admin/api/logs');renderLogs()}catch(e){console.error('loadLogs failed:',e)}}
function renderLogs(){var q=(document.getElementById('log-filter')?document.getElementById('log-filter').value:'').toLowerCase();var rows=state.logs.filter(function(l){return JSON.stringify(l).toLowerCase().includes(q)});document.getElementById('t-logs').innerHTML=rows.map(function(l){return '<tr><td class="mini">'+esc(l.time)+'</td><td class="mono">'+esc(l.ip)+'</td><td>'+esc(l.country)+'</td><td>'+esc(l.ide)+'</td><td class="truncate" title="'+esc(l.query||l.sys_prompt)+'">'+esc(l.query||l.sys_prompt)+'</td><td class="mono">'+esc(l.backend)+'</td><td>'+esc(l.intent)+'</td><td>'+esc(l.ms)+'ms</td><td>'+badge(l.success?'成功':'失败',l.success?'ok':'err')+'</td></tr>'}).join('')||'<tr><td colspan="9" class="empty">暂无日志</td></tr>'}
function exportLogsCSV(){var rows=state.logs||[];if(!rows.length){toast('暂无日志可导出','warn');return}var header='time,ip,country,ide,query,backend,intent,ms,success';var csv=[header].concat(rows.map(function(l){return [l.time,l.ip,l.country,l.ide,'"'+(l.query||'').replace(/"/g,'""')+'"',l.backend,l.intent,l.ms,l.success].join(',')})).join('\\n');var blob=new Blob([csv],{type:'text/csv'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='lima-logs-'+new Date().toISOString().slice(0,10)+'.csv';a.click();toast('已导出 CSV ('+rows.length+' 条)')}
function exportLogsJSON(){var rows=state.logs||[];if(!rows.length){toast('暂无日志可导出','warn');return}var blob=new Blob([JSON.stringify(rows,null,2)],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='lima-logs-'+new Date().toISOString().slice(0,10)+'.json';a.click();toast('已导出 JSON ('+rows.length+' 条)')}
async function loadBackends(){try{var res=await json('/admin/backends');state.backends=res.backends||[];renderBackends()}catch(e){console.error('loadBackends failed:',e)}}
function renderBackends(){var q=(document.getElementById('backend-filter')?document.getElementById('backend-filter').value:'').toLowerCase();var poolFilter=state._poolFilter||'all';var rows=state.backends.filter(function(b){if(poolFilter!=='all'&&(!b.pools||!b.pools.includes(poolFilter)))return false;return JSON.stringify(b).toLowerCase().includes(q)});document.getElementById('t-be-list').innerHTML=rows.map(function(b){var url=b.url||'';var shortUrl=url.length>45?url.substring(0,45)+'...':url;var keyStatus=b.key_configured?badge('已配置','ok'):badge('未配置','err');var caps=(b.caps||[]).slice(0,3).map(function(c){return badge(c,'off')}).join(' ');var pools=(b.pools||[]).map(function(p){return badge(p,p==='code'?'warn':p==='sandbox'?'off':'info')}).join(' ');var adm=b.admission?badge(b.admission,'warn'):'<span class="mini">默认</span>';var enabled=b.in_registry?badge('注册','ok'):badge('未注册','err');return '<tr><td><input type="checkbox" class="be-check" value="'+escJs(b.name)+'"></td><td>'+enabled+'</td><td class="mono">'+esc(b.name)+'</td><td class="truncate" title="'+esc(url)+'">'+esc(shortUrl)+'</td><td>'+esc(b.model)+'</td><td>'+keyStatus+'</td><td>'+esc(b.fmt)+'</td><td>'+caps+'</td><td>'+pools+'</td><td>'+adm+'</td><td>'+esc(b.total_calls||0)+'</td><td>'+esc(b.error_rate||'0%')+'</td><td><button class="btn ghost" onclick=\\'editBackend("'+escJs(b.name)+'")\\'>编辑</button> <button class="btn ghost" onclick=\\'testBackend("'+escJs(b.name)+'")\\'>测试</button> <button class="btn danger" onclick=\\'deleteBackend("'+escJs(b.name)+'")\\'>删除</button></td></tr>'}).join('')||'<tr><td colspan="13" class="empty">暂无后端</td></tr>';updateBatchBar()}
function filterPool(pool){state._poolFilter=pool;document.querySelectorAll('.filter-bar button').forEach(function(btn){btn.classList.remove('active')});var el=document.getElementById('pool-'+pool);if(el)el.classList.add('active');renderBackends()}
function getSelectedBackends(){var checks=document.querySelectorAll('.be-check:checked');var names=[];checks.forEach(function(c){names.push(c.value)});return names}
function toggleSelectAll(el){document.querySelectorAll('.be-check').forEach(function(c){c.checked=el.checked});updateBatchBar()}
function updateBatchBar(){var sel=getSelectedBackends();var bar=document.getElementById('batch-bar');if(!bar)return;if(sel.length>0){bar.style.display='block';document.getElementById('batch-count').textContent=sel.length+' 个已选'}else{bar.style.display='none'}}
document.addEventListener('change',function(e){if(e.target.classList&&e.target.classList.contains('be-check'))updateBatchBar()});
async function batchTest(){var sel=getSelectedBackends();if(!sel.length)return;toast('正在测试 '+sel.length+' 个后端...');var ok=0,fail=0;for(var i=0;i<sel.length;i++){try{var r=await json('/admin/backends/'+encodeURIComponent(sel[i])+'/test',{method:'POST'});if(r.ok)ok++;else fail++}catch(e){fail++}}toast('批量测试完成: '+ok+' 通过, '+fail+' 失败',fail?'warn':'ok')}
async function batchDisable(){var sel=getSelectedBackends();if(!sel.length||!confirm('确认禁用 '+sel.length+' 个后端?'))return;var ok=0;for(var i=0;i<sel.length;i++){try{await json('/admin/backends/'+encodeURIComponent(sel[i]),{method:'DELETE'});ok++}catch(e){}}toast('已禁用 '+ok+' 个后端');await loadBackends()}
async function batchEnable(){var sel=getSelectedBackends();if(!sel.length)return;toast('批量启用中...');var ok=0;for(var i=0;i<sel.length;i++){try{await json('/admin/backends/'+encodeURIComponent(sel[i]),{method:'POST',body:JSON.stringify({name:sel[i],url:'',model:'',key:'none',fmt:'openai'})});ok++}catch(e){}}toast('已启用 '+ok+' 个后端');await loadBackends()}
function setLoading(btnId,loading){var btn=document.getElementById(btnId);if(!btn)return;if(loading){btn._origText=btn.textContent;btn.textContent='处理中...';btn.disabled=true;state._loading=true}else{btn.textContent=btn._origText||btn.textContent;btn.disabled=false;state._loading=false}}
async function addBackend(){var body={name:v('be-name'),url:v('be-url'),model:v('be-model'),key:v('be-key'),fmt:v('be-fmt'),auth:v('be-auth'),tier:v('be-tier'),admission:v('be-admission')};if(!body.name){toast('请输入后端名称','warn');return}try{toast('正在添加...');var res=await json('/admin/backends',{method:'POST',body:JSON.stringify(body)});if(res.ok){toast('已添加 '+body.name);await loadBackends()}else{toast('添加失败: '+(res.detail||'未知错误'),'err')}}catch(e){toast('添加失败: '+e.message,'err')}}
async function testBackend(name){try{toast('正在测试 '+name+'...');var res=await json('/admin/backends/'+encodeURIComponent(name)+'/test',{method:'POST'});if(res.ok){toast(name+' 测试通过 ('+res.latency_ms+'ms, HTTP '+res.status+')')}else{toast(name+' 测试失败 (HTTP '+(res.status||'?')+', '+(res.error||'未知错误')+')',res.latency_ms>10000?'warn':'err')}}catch(e){toast('测试失败: '+e.message,'err')}}
async function deleteBackend(name){if(!confirm('确认删除后端 '+name+' ?'))return;try{toast('正在删除...');await json('/admin/backends/'+encodeURIComponent(name),{method:'DELETE'});toast('已删除 '+name);await loadBackends()}catch(e){toast('删除失败: '+e.message,'err')}}
function editBackend(name){var b=state.backends.find(function(x){return x.name===name});if(!b){toast('后端不存在','err');return}var newUrl=prompt('API URL',b.url||'');if(newUrl===null)return;var newModel=prompt('模型名称',b.model||'');if(newModel===null)return;var newCaps=prompt('能力 (逗号分隔)',(b.caps||[]).join(','));if(newCaps===null)return;var newAdm=prompt('准入策略 (空=默认, code_medium_candidate=编程池, sandbox_only=沙箱)',b.admission||'');if(newAdm===null)return;var body={url:newUrl,model:newModel,caps:newCaps.split(',').filter(function(x){return x.trim()}),admission:newAdm};toast('正在更新...');json('/admin/backends/'+encodeURIComponent(name),{method:'PUT',body:JSON.stringify(body)}).then(function(res){if(res.ok){toast('已更新 '+name);loadBackends()}else{toast('更新失败: '+(res.detail||'未知错误'),'err')}}).catch(function(e){toast('更新失败: '+e.message,'err')})}
function v(id){var el=document.getElementById(id);return el?el.value.trim():''}
async function loadModel(){try{state.model=await json('/admin/api/model-status');renderModel()}catch(e){console.error('loadModel failed:',e)}}
function renderModel(){var d=state.model||{};document.getElementById('m-name').textContent=d.model||'-';document.getElementById('m-accuracy').textContent=d.accuracy||'-';document.getElementById('m-data').textContent=d.data_count||0;document.getElementById('s-fallbacks').textContent=d.fallback_log_count||0;var rows=d.recent_fallbacks||[];document.getElementById('t-fallbacks').innerHTML=rows.slice().reverse().map(function(x){return '<tr><td class="mini">'+esc(x.time||x.timestamp||'')+'</td><td class="truncate">'+esc(x.query||x.prompt||'')+'</td><td class="mono">'+esc(x.original_backend||x.backend||'')+'</td><td>'+esc(x.intent||x.reason||'')+'</td></tr>'}).join('')||'<tr><td colspan="4" class="empty">暂无 fallback</td></tr>'}
async function triggerRetrain(){if(!confirm('确认触发 auto_retrain.py --force ?'))return;try{toast('正在触发重训...');var r=await json('/admin/api/retrain',{method:'POST'});toast('训练任务: '+(r.job_id||r.status||'已启动'));loadRetrainJobs()}catch(e){toast('触发失败: '+e.message,'err')}}
async function loadRetrainJobs(){try{var d=await json('/admin/api/retrain/jobs');renderRetrainJobs(d.jobs||[])}catch(e){}}
function renderRetrainJobs(jobs){var el=document.getElementById('retrain-progress');if(!el||!jobs.length){if(el)el.innerHTML='';return}var html=jobs.slice(0,5).map(function(j){var sc=j.status==='completed'?'ok':j.status==='running'?'warn':j.status==='failed'||j.status==='error'?'err':'off';var elapsed=j.finished_at?Math.round(j.finished_at-j.started_at)+'s':'进行中';var out=(j.output||'').substring(0,80);return '<div style="display:flex;gap:10px;align-items:center;padding:8px 12px;border:1px solid var(--line);border-radius:10px;margin-bottom:6px"><span class="mono" style="font-size:11px;color:var(--muted)">'+esc(j.job_id)+'</span>'+badge(j.status,sc)+'<span class="mini">'+elapsed+'</span>'+(out?'<span class="mini truncate" title="'+esc(j.output)+'">'+esc(out)+'</span>':'')+'</div>'}).join('');el.innerHTML=html}
async function loadHealth(){try{var d=await json('/admin/api/backend-health');state.health=d;renderHealth()}catch(e){console.error('loadHealth failed:',e)}}
function renderHealth(){var d=state.health||{};var s=d.summary||{};document.getElementById('h-healthy').textContent=s.healthy||0;document.getElementById('h-degraded').textContent=s.degraded||0;document.getElementById('h-dead').textContent=s.dead||0;document.getElementById('h-cooled').textContent=s.cooled||0;var rows=(d.backends||[]).slice().sort(function(a,b){var order={dead:0,degraded:1,healthy:2};return(order[a.health]||3)-(order[b.health]||3)||b.score-a.score});document.getElementById('t-health').innerHTML=rows.map(function(b){var hb=b.health==='healthy'?'ok':b.health==='degraded'?'warn':b.health==='dead'?'err':'off';var cb=b.cb_state==='closed'?'ok':b.cb_state==='open'?'err':'warn';return '<tr><td class="mono">'+esc(b.name)+'</td><td>'+badge(b.health,hb)+'</td><td>'+esc(b.score)+'</td><td>'+esc(Math.round(b.avg_latency_ms))+'</td><td>'+badge(b.cb_state,cb)+'</td><td>'+esc(b.cb_failures)+'</td><td>'+esc(b.cb_total_calls)+'</td><td>'+esc(b.consecutive_failures)+'</td><td>'+(b.cooldown_remaining_s>0?esc(Math.round(b.cooldown_remaining_s))+'s':'-')+'</td><td>'+(b.last_error_code?badge('HTTP '+b.last_error_code,'err'):'-')+'</td></tr>'}).join('')||'<tr><td colspan="10" class="empty">暂无健康数据</td></tr>'}
async function loadFallbackAnalysis(){try{var d=await json('/admin/api/fallback-analysis');state.fallbackAnalysis=d;renderFallbackAnalysis()}catch(e){console.error('loadFallbackAnalysis failed:',e)}}
function renderFallbackAnalysis(){var d=state.fallbackAnalysis;if(!d)return;var total=d.total||0;var bb=d.by_backend||[];var bi=d.by_intent||[];var ht=d.hourly_trend||[];var bbHtml=bb.slice(0,5).map(function(x){var pct=total?Math.round(x.count/total*100):0;return '<tr><td class="mono">'+esc(x.backend)+'</td><td>'+x.count+'</td><td>'+pct+'%</td><td><div class="spark"><span style="width:'+pct+'%"></span></div></td></tr>'}).join('')||'<tr><td colspan="4" class="empty">暂无数据</td></tr>';var biHtml=bi.slice(0,5).map(function(x){var pct=total?Math.round(x.count/total*100):0;return '<tr><td>'+esc(x.intent)+'</td><td>'+x.count+'</td><td>'+pct+'%</td></tr>'}).join('')||'<tr><td colspan="3" class="empty">暂无数据</td></tr>';var maxHt=Math.max.apply(null,[1].concat(ht.map(function(x){return x.count})));var htHtml=ht.slice(-12).map(function(x){return '<div style="display:inline-block;width:'+(100/12)+'%;vertical-align:bottom;padding:0 2px"><div style="background:linear-gradient(var(--amber),var(--red));width:100%;height:'+Math.round(x.count/maxHt*100)+'%;min-height:2px;border-radius:3px 3px 0 0"></div><div class="mini" style="text-align:center;margin-top:4px">'+esc(x.hour.slice(11,13))+'h</div></div>'}).join('');var el1=document.getElementById('fb-by-backend');if(el1)el1.innerHTML=bbHtml;var el2=document.getElementById('fb-by-intent');if(el2)el2.innerHTML=biHtml;var el3=document.getElementById('fb-hourly');if(el3)el3.innerHTML=htHtml;var el4=document.getElementById('fb-total');if(el4)el4.textContent=total}
async function loadRetrieval(){try{state.traces=await json('/admin/api/retrieval-traces');renderRetrieval()}catch(e){console.error('loadRetrieval failed:',e)}}
function renderRetrieval(){var rows=Array.isArray(state.traces)?state.traces:[];var count=rows.length;var avgCand=0,avgPrec=0,useful=0;if(count>0){rows.forEach(function(t){avgCand+=Number(t.candidates_searched||0);avgPrec+=Number(t.retrieval_precision||0);useful+=t.injection_useful?1:0});avgCand=Math.round(avgCand/count);avgPrec=Math.round(avgPrec*100/count);useful=Math.round(useful/count*100)}document.getElementById('r-count').textContent=count;document.getElementById('r-avg-cand').textContent=avgCand;document.getElementById('r-avg-prec').textContent=avgPrec+'%';document.getElementById('r-useful').textContent=useful+'%';document.getElementById('t-retrieval').innerHTML=rows.map(function(t){var ts=t.timestamp?new Date(t.timestamp*1000).toLocaleTimeString():'';var be=t.backend||'';var q=(t.query_entities||[]).join(', ');var cand=t.candidates_searched||0;var inj=t.injected_chars||0;var prec=t.retrieval_precision!=null?Math.round(t.retrieval_precision*100)+'%':'-';var uf=t.injection_useful?badge('✓','ok'):badge('✗','err');var sc=t.scenario||t.request_type||'';return '<tr><td>'+esc(ts)+'</td><td class="mono">'+esc(be)+'</td><td class="truncate">'+esc(q)+'</td><td>'+cand+'</td><td>'+inj+'</td><td>'+prec+'</td><td>'+uf+'</td><td>'+esc(sc)+'</td></tr>'}).join('')||'<tr><td colspan="8" class="empty">暂无检索追踪</td></tr>'}
async function loadKeyUrl(){try{var d=await json('/admin/api/key-url-inventory');state.keyUrl=d;renderKeyUrlTable();renderKeyPools()}catch(e){console.error('loadKeyUrl failed:',e)}}
function renderKeyUrlTable(){var d=state.keyUrl||{};var q=(document.getElementById('key-filter')?document.getElementById('key-filter').value:'').toLowerCase();var rows=(d.backends||[]).filter(function(b){return JSON.stringify(b).toLowerCase().includes(q)});document.getElementById('t-key-url').innerHTML=rows.map(function(b){var url=b.url||'';var keyBadge=b.key_configured?badge(b.key_masked,'info'):badge('未配置','err');return '<tr><td class="mono">'+esc(b.name)+'</td><td class="truncate" title="'+esc(url)+'">'+esc(url.length>55?url.substring(0,55)+'...':url)+'</td><td>'+keyBadge+'</td><td>'+esc(b.model)+'</td><td>'+esc(b.fmt)+'</td><td><button class="btn ghost" onclick="testBackend(\\''+escJs(b.name)+'\\')">测试</button></td></tr>'}).join('')||'<tr><td colspan="6" class="empty">暂无后端</td></tr>'}
function renderKeyPools(){var d=state.keyUrl||{};var pools=(d.key_pools||{}).providers||{};var el=document.getElementById('key-pool-info');if(!el)return;var names=Object.keys(pools).sort();if(!names.length){el.innerHTML='<div class="empty">暂无 Provider Key Pool</div>';return}var html=names.map(function(p){var pool=pools[p];return '<div style="margin-bottom:12px;padding:12px 14px;border:1px solid var(--line);border-radius:12px"><div style="display:flex;gap:12px;align-items:center;margin-bottom:6px"><span class="mono" style="font-weight:700;color:var(--cyan)">'+esc(p)+'</span>'+badge(pool.active+' active','ok')+badge(pool.cooled+' cooled','warn')+badge(pool.blocked+' blocked','err')+'</div><div style="display:flex;gap:6px;flex-wrap:wrap">'+(pool.entries||[]).map(function(e){var sc=e.status==='active'?'ok':e.status==='cooled'?'warn':'err';return '<span style="font-size:11px;padding:3px 8px;border-radius:8px;background:rgba(148,163,184,0.1);border:1px solid var(--line)" class="badge badge-'+sc+'">'+esc(e.key_id)+' w='+e.weight+(e.cool_remaining_sec>0?' cd='+e.cool_remaining_sec+'s':'')+'</span>'}).join('')+'</div></div>'}).join('');el.innerHTML=html}
async function loadAgents(){try{var d=await json('/admin/api/agent-audit?limit=50');state.agents=d.tasks||[];renderAgents()}catch(e){console.error('loadAgents failed:',e)}}
function renderAgents(){document.getElementById('t-agent-audit').innerHTML=state.agents.map(function(t){return '<tr><td class="mono">'+esc(t.task_id||t.id)+'</td><td>'+badge(t.status||'-',String(t.status).indexOf('fail')>=0?'err':String(t.status).indexOf('review')>=0?'warn':'ok')+'</td><td>'+esc(t.mode)+'</td><td class="truncate">'+esc(t.repo)+'</td><td class="truncate" title="'+esc(t.goal)+'">'+esc(t.goal)+'</td><td>'+esc(t.events_count!=null?t.events_count:t.event_count!=null?t.event_count:'')+'</td><td>'+esc(t.next_action||'')+'</td></tr>'}).join('')||'<tr><td colspan="7" class="empty">暂无 Agent 任务</td></tr>'}

var _agentTasksFilter='';
var _agentTasksData=[];

async function loadAgentTasks(){try{var d=await json('/admin/api/agent-tasks?limit=100');_agentTasksData=d.tasks||[];renderAgentTasks();renderAgentTaskStats()}catch(e){console.error('loadAgentTasks failed:',e)}}
function renderAgentTaskStats(){var tasks=_agentTasksData;var total=tasks.length,running=0,completed=0,failed=0;
tasks.forEach(function(t){var s=t.status||'';if(s==='running'||s==='claimed')running++;else if(s==='completed')completed++;else if(s==='failed')failed++});
document.getElementById('at-total').textContent=total;
document.getElementById('at-running').textContent=running;
document.getElementById('at-completed').textContent=completed;
document.getElementById('at-failed').textContent=failed}
function renderAgentTasks(){var q=(document.getElementById('at-filter')?document.getElementById('at-filter').value:'').toLowerCase();var filter=_agentTasksFilter;var rows=_agentTasksData.filter(function(t){if(filter&&t.status!==filter)return false;if(q&&!JSON.stringify(t).toLowerCase().includes(q))return false;return true});document.getElementById('t-agent-tasks').innerHTML=rows.map(function(t){var sc=t.status==='completed'?'ok':t.status==='failed'?'err':t.status==='running'?'warn':'off';var created=t.created_at?new Date(t.created_at*1000).toLocaleString():'-';var desc=(t.description||'').substring(0,60);var taskId=t.task_id||'';var shortId=taskId.length>12?taskId.substring(0,12)+'...':taskId;var actions='';if(t.status!=='completed'&&t.status!=='failed'&&t.status!=='cancelled'){actions+='<button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="cancelAgentTask(\''+escJs(taskId)+'\')">取消</button> '}
if(t.status==='failed'||t.status==='quarantined'){actions+='<button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="retryAgentTask(\''+escJs(taskId)+'\')">重试</button> '}
actions+='<button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="showAgentTaskDetail(\''+escJs(taskId)+'\')">详情</button>';
return '<tr><td class="mono" title="'+esc(taskId)+'">'+esc(shortId)+'</td><td>'+badge(t.status,sc)+'</td><td class="mono">'+esc(t.worker_id||'-')+'</td><td class="mono">'+esc(t.backend||'-')+'</td><td class="truncate" title="'+esc(desc)+'">'+esc(desc)+'</td><td class="mini">'+esc(created)+'</td><td>'+actions+'</td></tr>'}).join('')||'<tr><td colspan="7" class="empty">暂无 Agent 任务</td></tr>'}
function filterAgentTasks(filter){_agentTasksFilter=filter;document.querySelectorAll('#panel-agent-tasks .filter-bar button').forEach(function(b){b.classList.remove('active')});var id=filter?'at-'+filter:'at-all';var el=document.getElementById(id);if(el)el.classList.add('active');renderAgentTasks()}
async function cancelAgentTask(taskId){if(!confirm('确认取消任务 '+taskId+' ?'))return;try{await json('/admin/api/agent-tasks/'+encodeURIComponent(taskId)+'/cancel',{method:'POST'});toast('已请求取消任务');await loadAgentTasks()}catch(e){toast('取消失败: '+e.message,'err')}}
async function retryAgentTask(taskId){if(!confirm('确认重试任务 '+taskId+' ?'))return;try{await json('/admin/api/agent-tasks/'+encodeURIComponent(taskId)+'/retry',{method:'POST'});toast('已重试任务');await loadAgentTasks()}catch(e){toast('重试失败: '+e.message,'err')}}
async function showAgentTaskDetail(taskId){try{var d=await json('/admin/api/agent-tasks/'+encodeURIComponent(taskId));var el=document.getElementById('at-detail-card');var content=document.getElementById('at-detail-content');el.style.display='block';var sc=d.status==='completed'?'ok':d.status==='failed'?'err':d.status==='running'?'warn':'off';var html='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px">';
html+='<div><span class="metric-label">Task ID</span><div class="mono" style="color:var(--cyan)">'+esc(d.task_id)+'</div></div>';
html+='<div><span class="metric-label">状态</span><div>'+badge(d.status,sc)+'</div></div>';
html+='<div><span class="metric-label">创建时间</span><div class="mini">'+esc(d.created_at?new Date(d.created_at*1000).toLocaleString():'-')+'</div></div>';
html+='<div><span class="metric-label">更新时间</span><div class="mini">'+esc(d.updated_at?new Date(d.updated_at*1000).toLocaleString():'-')+'</div></div>';
html+='</div>';
if(d.request){html+='<div style="margin-bottom:16px"><h3 style="font-size:14px;color:var(--muted);margin-bottom:8px">请求内容</h3><pre style="background:rgba(8,12,20,0.6);border:1px solid var(--line);border-radius:12px;padding:12px;font-size:12px;max-height:200px;overflow:auto">'+esc(JSON.stringify(d.request,null,2))+'</pre></div>'}
if(d.result){html+='<div style="margin-bottom:16px"><h3 style="font-size:14px;color:var(--muted);margin-bottom:8px">执行结果</h3><pre style="background:rgba(8,12,20,0.6);border:1px solid var(--line);border-radius:12px;padding:12px;font-size:12px;max-height:200px;overflow:auto">'+esc(JSON.stringify(d.result,null,2))+'</pre></div>'}
if(d.events&&d.events.length){html+='<div><h3 style="font-size:14px;color:var(--muted);margin-bottom:8px">事件日志 ('+d.events.length+')</h3><div class="table-wrap"><table><thead><tr><th>时间</th><th>事件</th></tr></thead><tbody>';
d.events.forEach(function(e){var ts=e.ts?new Date(e.ts*1000).toLocaleTimeString():'-';var evt=JSON.stringify(e);if(evt.length>100)evt=evt.substring(0,100)+'...';html+='<tr><td class="mini">'+esc(ts)+'</td><td class="truncate" title="'+esc(JSON.stringify(e))+'">'+esc(evt)+'</td></tr>'});
html+='</tbody></table></div></div>'}
content.innerHTML=html}catch(e){toast('加载详情失败: '+e.message,'err')}}
function hideTaskDetail(){document.getElementById('at-detail-card').style.display='none'}
// ── Live Logs SSE ───────────────────────────────────────────────────────
var _liveLogs=[];
var _liveLogCount=0;
var _liveLogSuccess=0;
var _liveLogFail=0;
var _liveLogEventSource=null;
function toggleLiveLogs(){if(_liveLogEventSource){_liveLogEventSource.close();_liveLogEventSource=null;document.getElementById('ll-status').textContent='已断开';document.getElementById('ll-toggle').textContent='开始监听';return}document.getElementById('ll-status').textContent='连接中...';_liveLogEventSource=new EventSource('/admin/api/logs/stream');_liveLogEventSource.onopen=function(){document.getElementById('ll-status').textContent='已连接';document.getElementById('ll-toggle').textContent='停止监听'};_liveLogEventSource.onmessage=function(ev){try{var d=JSON.parse(ev.data);_liveLogs.unshift(d);if(_liveLogs.length>200)_liveLogs.pop();_liveLogCount++;if(d.success)_liveLogSuccess++;else _liveLogFail++;document.getElementById('ll-count').textContent=_liveLogCount;document.getElementById('ll-success').textContent=_liveLogSuccess;document.getElementById('ll-fail').textContent=_liveLogFail;renderLiveLogs()}catch(e){}};_liveLogEventSource.onerror=function(){document.getElementById('ll-status').textContent='连接错误';_liveLogEventSource.close();_liveLogEventSource=null;document.getElementById('ll-toggle').textContent='开始监听'}}
function filterLiveLogs(){renderLiveLogs()}
function renderLiveLogs(){var q=(document.getElementById('ll-filter')?document.getElementById('ll-filter').value:'').toLowerCase();var rows=_liveLogs.filter(function(l){return JSON.stringify(l).toLowerCase().includes(q)}).slice(0,100);document.getElementById('t-live-logs').innerHTML=rows.map(function(l){return '<tr><td class="mini">'+esc(l.time)+'</td><td class="mono">'+esc(l.ip)+'</td><td>'+esc(l.country)+'</td><td>'+esc(l.ide)+'</td><td class="truncate" title="'+esc(l.query||l.sys_prompt)+'">'+esc(l.query||l.sys_prompt)+'</td><td class="mono">'+esc(l.backend)+'</td><td>'+esc(l.intent)+'</td><td>'+esc(l.ms)+'ms</td><td>'+badge(l.success?'成功':'失败',l.success?'ok':'err')+'</td></tr>'}).join('')||'<tr><td colspan="9" class="empty">等待日志...</td></tr>'}
function clearLiveLogs(){_liveLogs=[];_liveLogCount=0;_liveLogSuccess=0;_liveLogFail=0;document.getElementById('ll-count').textContent='0';document.getElementById('ll-success').textContent='0';document.getElementById('ll-fail').textContent='0';renderLiveLogs()}

// ── Config Import/Export ──────────────────────────────────────────────────
var _configData=null;
async function loadConfig(){try{var d=await json('/admin/api/config/export');_configData=d;document.getElementById('cfg-version').textContent=d.version||'-';document.getElementById('cfg-preview').textContent=JSON.stringify(d,null,2)}catch(e){document.getElementById('cfg-preview').textContent='加载失败: '+e.message}}
async function exportConfig(){try{var d=await json('/admin/api/config/export');var blob=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='lima-config-'+new Date().toISOString().slice(0,10)+'.json';a.click();toast('已导出配置')}catch(e){toast('导出失败: '+e.message,'err')}}
async function importConfig(){var fileInput=document.getElementById('config-file');if(!fileInput||!fileInput.files.length){toast('请选择配置文件','warn');return}var file=fileInput.files[0];try{var text=await file.text();var data=JSON.parse(text);if(!data.version){toast('无效的配置文件格式','err');return}if(!confirm('确认导入配置？这将覆盖现有配置。'))return;var res=await json('/admin/api/config/import',{method:'POST',body:JSON.stringify(data)});if(res.ok){toast('已导入配置: '+res.imported.join(', '));loadConfig()}else{toast('导入失败','err')}}catch(e){toast('导入失败: '+e.message,'err')}}

// ── Device Management ──────────────────────────────────────────────────────
var _deviceData=[];
async function loadDevices(){try{var d=await json('/admin/api/devices');_deviceData=d.devices||[];renderDevices();document.getElementById('dev-total').textContent=_deviceData.length;var mqtt=0,ws=0,tasks=0;_deviceData.forEach(function(dev){tasks+=dev.inflight_count||0});document.getElementById('dev-tasks').textContent=tasks}catch(e){console.error('loadDevices failed:',e)}}
function renderDevices(){document.getElementById('t-devices').innerHTML=_deviceData.map(function(dev){var uptime=dev.last_uptime_ms?Math.round(dev.last_uptime_ms/1000)+'s':'-';var caps=(dev.capabilities||[]).slice(0,4).map(function(c){return badge(c,'off')}).join(' ');return '<tr><td class="mono">'+esc(dev.device_id)+'</td><td class="mono">'+esc(dev.fw_rev||'-')+'</td><td>'+caps+'</td><td>'+uptime+'</td><td>'+(dev.inflight_count||0)+'</td><td><button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="showDeviceDetail(\''+escJs(dev.device_id)+'\')">详情</button> <button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="restartDevice(\''+escJs(dev.device_id)+'\')">重启</button></td></tr>'}).join('')||'<tr><td colspan="6" class="empty">无在线设备</td></tr>'}
async function showDeviceDetail(deviceId){try{var d=await json('/admin/api/devices/'+encodeURIComponent(deviceId));var info='Device ID: '+d.device_id+'\n固件: '+d.fw_rev+'\n能力: '+(d.capabilities||[]).join(', ')+'\n运行时间: '+Math.round(d.last_uptime_ms/1000)+'s\n待处理任务: '+(d.inflight_tasks||[]).length;alert(info)}catch(e){toast('加载详情失败: '+e.message,'err')}}
async function restartDevice(deviceId){if(!confirm('确认重启设备 '+deviceId+' ?'))return;try{await json('/admin/api/devices/'+encodeURIComponent(deviceId)+'/restart',{method:'POST'});toast('已发送重启命令');setTimeout(loadDevices,2000)}catch(e){toast('重启失败: '+e.message,'err')}}

// ── Alert Rules ────────────────────────────────────────────────────────────
var _alertRules=[];
async function loadAlerts(){try{var d=await json('/admin/api/alerts/rules');_alertRules=d.rules||[];renderAlerts();document.getElementById('alert-total').textContent=_alertRules.length;var active=0;_alertRules.forEach(function(r){if(r.enabled)active++});document.getElementById('alert-active').textContent=active}catch(e){console.error('loadAlerts failed:',e)}}
function renderAlerts(){document.getElementById('t-alerts').innerHTML=_alertRules.map(function(r){var metricNames={error_rate:'错误率',latency_ms:'延迟',fallback_rate:'Fallback率',request_count:'请求量'};var condNames={gt:'>',lt:'<',eq:'='};return '<tr><td class="mono" style="font-size:11px">'+esc(r.rule_id)+'</td><td>'+esc(r.name)+'</td><td>'+esc(metricNames[r.metric]||r.metric)+'</td><td>'+esc(condNames[r.condition]||r.condition)+' '+esc(r.threshold)+'</td><td>'+esc(r.threshold)+'</td><td>'+esc(r.window_sec)+'s</td><td>'+badge(r.enabled?'启用':'禁用',r.enabled?'ok':'off')+'</td><td><button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="toggleAlert(\''+escJs(r.rule_id)+'\','+(!r.enabled)+')">'+(r.enabled?'禁用':'启用')+'</button> <button class="btn danger" style="font-size:11px;padding:4px 8px" onclick="deleteAlert(\''+escJs(r.rule_id)+'\')">删除</button></td></tr>'}).join('')||'<tr><td colspan="8" class="empty">暂无告警规则</td></tr>'}
function showAddAlert(){document.getElementById('alert-add-form').style.display='block'}
function hideAddAlert(){document.getElementById('alert-add-form').style.display='none'}
async function addAlertRule(){var body={name:v('al-name'),metric:v('al-metric'),condition:v('al-condition'),threshold:parseFloat(v('al-threshold'))||0.5,window_sec:parseInt(v('al-window'))||300};if(!body.name){toast('请输入规则名称','warn');return}try{await json('/admin/api/alerts/rules',{method:'POST',body:JSON.stringify(body)});toast('已创建告警规则');hideAddAlert();loadAlerts()}catch(e){toast('创建失败: '+e.message,'err')}}
async function toggleAlert(ruleId,enabled){try{await json('/admin/api/alerts/rules/'+encodeURIComponent(ruleId),{method:'PUT',body:JSON.stringify({enabled:enabled})});toast('已更新规则');loadAlerts()}catch(e){toast('更新失败: '+e.message,'err')}}
async function deleteAlert(ruleId){if(!confirm('确认删除告警规则 '+ruleId+' ?'))return;try{await json('/admin/api/alerts/rules/'+encodeURIComponent(ruleId),{method:'DELETE'});toast('已删除告警规则');loadAlerts()}catch(e){toast('删除失败: '+e.message,'err')}}

// ── Client Key Management ──────────────────────────────────────────────────
var _clientKeysData=[];
async function loadClientKeys(){try{var d=await json('/admin/api/client-keys');_clientKeysData=d.keys||[];renderClientKeys();var total=_clientKeysData.length,en=0,dis=0,activeToday=0;_clientKeysData.forEach(function(k){if(k.enabled)en++;else dis++;if(k.usage_daily>0)activeToday++});document.getElementById('ck-total').textContent=total;document.getElementById('ck-enabled').textContent=en;document.getElementById('ck-disabled').textContent=dis;document.getElementById('ck-active-today').textContent=activeToday}catch(e){console.error('loadClientKeys failed:',e)}}
function renderClientKeys(){document.getElementById('t-client-keys').innerHTML=_clientKeysData.map(function(k){var lastUsed=k.last_used_at?new Date(k.last_used_at*1000).toLocaleString():'-';var urls=(k.allowed_urls||['*']).join(', ');return '<tr><td class="mono" title="'+esc(k.key_masked)+'">'+esc(k.key_masked)+'</td><td>'+esc(k.label)+'</td><td>'+badge(k.enabled?'启用':'禁用',k.enabled?'ok':'off')+'</td><td>'+esc(k.quota_daily)+'</td><td>'+esc(k.quota_monthly)+'</td><td>'+esc(k.usage_daily)+'</td><td>'+esc(k.usage_monthly)+'</td><td class="mini">'+esc(lastUsed)+'</td><td class="truncate" title="'+esc(urls)+'">'+esc(urls)+'</td><td><button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="editClientKey(\''+escJs(k.key_id)+'\')">编辑</button> <button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="toggleClientKey(\''+escJs(k.key_id)+'\','+(!k.enabled)+')">'+(k.enabled?'禁用':'启用')+'</button> <button class="btn ghost" style="font-size:11px;padding:4px 8px" onclick="regenerateClientKey(\''+escJs(k.key_id)+'\')">重新生成</button> <button class="btn danger" style="font-size:11px;padding:4px 8px" onclick="deleteClientKey(\''+escJs(k.key_id)+'\')">删除</button></td></tr>'}).join('')||'<tr><td colspan="10" class="empty">暂无客户端 Key</td></tr>'}
function showCreateKeyForm(){var label=prompt('Key 标签 (例如: 给Cursor用户的key)');if(!label)return;var daily=prompt('日限额 (默认 1000, 0=无限)','1000');if(daily===null)return;var monthly=prompt('月限额 (默认 30000, 0=无限)','30000');if(monthly===null)return;var rpm=prompt('每分钟请求数限制 (默认 20)','20');if(rpm===null)return;var urls=prompt('允许的 URL (逗号分隔, * = 全部)','*');if(urls===null)return;var body={label:label,quota_daily:parseInt(daily)||1000,quota_monthly:parseInt(monthly)||30000,rate_limit_rpm:parseInt(rpm)||20,allowed_urls:urls.split(',').map(function(u){return u.trim()}).filter(function(u){return u})};toast('正在发放 Key...');json('/admin/api/client-keys',{method:'POST',body:JSON.stringify(body)}).then(function(res){if(res.ok){toast('Key 已发放! Key Value: '+res.key_value);alert('请保存此 Key (不会再次显示):\n\n'+res.key_value);loadClientKeys()}else{toast('发放失败: '+(res.detail||'未知错误'),'err')}}).catch(function(e){toast('发放失败: '+e.message,'err')})}
function editClientKey(keyId){var k=_clientKeysData.find(function(x){return x.key_id===keyId});if(!k){toast('Key 不存在','err');return}var label=prompt('标签',k.label||'');if(label===null)return;var daily=prompt('日限额',String(k.quota_daily||0));if(daily===null)return;var monthly=prompt('月限额',String(k.quota_monthly||0));if(monthly===null)return;var rpm=prompt('每分钟限制',String(k.rate_limit_rpm||20));if(rpm===null)return;var urls=prompt('允许 URL (逗号分隔)',(k.allowed_urls||['*']).join(','));if(urls===null)return;var body={label:label,quota_daily:parseInt(daily)||0,quota_monthly:parseInt(monthly)||0,rate_limit_rpm:parseInt(rpm)||20,allowed_urls:urls.split(',').map(function(u){return u.trim()}).filter(function(u){return u})};toast('正在更新...');json('/admin/api/client-keys/'+encodeURIComponent(keyId),{method:'PUT',body:JSON.stringify(body)}).then(function(res){if(res.ok){toast('已更新');loadClientKeys()}else{toast('更新失败','err')}}).catch(function(e){toast('更新失败: '+e.message,'err')})}
async function toggleClientKey(keyId,enabled){try{await json('/admin/api/client-keys/'+encodeURIComponent(keyId),{method:'PUT',body:JSON.stringify({enabled:enabled})});toast(enabled?'已启用':'已禁用');loadClientKeys()}catch(e){toast('操作失败: '+e.message,'err')}}
async function regenerateClientKey(keyId){if(!confirm('确认重新生成此 Key? 旧 Key 将立即失效。'))return;try{var res=await json('/admin/api/client-keys/'+encodeURIComponent(keyId)+'/regenerate',{method:'POST'});toast('Key 已重新生成');alert('新 Key Value:\n\n'+res.key_value);loadClientKeys()}catch(e){toast('重新生成失败: '+e.message,'err')}}
async function deleteClientKey(keyId){if(!confirm('确认删除此 Key? 操作不可恢复。'))return;try{await json('/admin/api/client-keys/'+encodeURIComponent(keyId),{method:'DELETE'});toast('已删除');loadClientKeys()}catch(e){toast('删除失败: '+e.message,'err')}}

var panelLoaders={overview:loadStats,traffic:loadLogs,backends:loadBackends,retrieval:loadRetrieval,model:function(){return Promise.all([loadModel(),loadFallbackAnalysis()])},health:loadHealth,'client-keys':loadClientKeys,keys:loadKeyUrl,agents:loadAgents,'agent-tasks':loadAgentTasks,config:loadConfig,devices:loadDevices,alerts:loadAlerts,'live-logs':function(){return Promise.resolve()}};
document.querySelectorAll('#nav button').forEach(function(btn){btn.addEventListener('click',function(){document.querySelectorAll('#nav button').forEach(function(x){x.classList.remove('active')});document.querySelectorAll('.section').forEach(function(x){x.classList.remove('active')});btn.classList.add('active');document.getElementById('panel-'+btn.dataset.panel).classList.add('active');var loader=panelLoaders[btn.dataset.panel];if(loader){setRefreshStatus('加载中...');loader().then(function(){setRefreshStatus('已刷新 '+new Date().toLocaleTimeString())}).catch(function(e){setRefreshStatus('加载失败');console.error(e)})}})});
refreshAll();setInterval(refreshAll,10000);
</script>
</body>
</html>'''

LOGIN_HTML = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>&#x674e;&#x9a6c;&#x7ba1;&#x7406;&#x9762;&#x677f; - &#x767b;&#x5f55;</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 20% 0%,rgba(53,213,255,.2),transparent 30%),#07111f;color:#e8f1ff;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.card{width:min(420px,calc(100% - 32px));padding:30px;border:1px solid rgba(145,166,210,.2);border-radius:28px;background:rgba(15,27,50,.88);box-shadow:0 18px 55px rgba(0,0,0,.38)}h1{margin:0 0 8px}.muted{color:#8fa3c7}input{width:100%;box-sizing:border-box;margin:18px 0 12px;border:1px solid rgba(145,166,210,.22);border-radius:14px;background:#07111f;color:#e8f1ff;padding:13px}button{width:100%;border:0;border-radius:14px;background:linear-gradient(135deg,#35d5ff,#a78bfa);color:#07111f;font-weight:900;padding:12px;cursor:pointer}.err{color:#fecdd3;background:rgba(251,113,133,.13);border:1px solid rgba(251,113,133,.28);padding:10px;border-radius:12px;margin-bottom:12px}</style></head><body><form class="card" method="post" action="/admin/login"><h1>&#x674e;&#x9a6c;&#x7ba1;&#x7406;&#x9762;&#x677f;</h1><p class="muted">&#x8f93;&#x5165;&#x7ba1;&#x7406;&#x5458; Token &#x8fdb;&#x5165;&#x751f;&#x4ea7;&#x63a7;&#x5236;&#x53f0;&#x3002;</p>{error}<input name="token" placeholder="Admin Token" type="password" autofocus><button type="submit">&#x767b;&#x5f55;</button></form></body></html>'

def render_admin_login(error: str = "") -> str:
    error_html = '<p class="err">' + error + '</p>' if error else ""
    return LOGIN_HTML.replace("{error}", error_html)


def render_admin_dashboard() -> str:
    return ADMIN_HTML
