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
<button data-panel="agents">Agent 审计</button>
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
<div class="card wide"><h2>后端调用排行 <span class="mini">成功率 / 平均耗时</span></h2><div class="table-wrap"><table><thead><tr><th>后端</th><th>调用</th><th>成功率</th><th>平均 ms</th><th>热度</th></tr></thead><tbody id="t-backends"></tbody></table></div></div>
<div class="card"><h2>意图分布</h2><div class="table-wrap"><table><thead><tr><th>意图</th><th>数量</th><th>占比</th></tr></thead><tbody id="t-intents"></tbody></table></div></div>
<div class="card full"><h2>IDE / 入口分布</h2><div id="ide-bars"></div></div>
</div>
</section>

<section id="panel-traffic" class="section"><div class="bento"><div class="card full"><h2>最近请求 <input class="search" id="log-filter" placeholder="搜索 IP / query / backend / intent" oninput="renderLogs()"></h2><div class="table-wrap"><table><thead><tr><th>时间</th><th>IP</th><th>地区</th><th>IDE</th><th>Query</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead><tbody id="t-logs"></tbody></table></div></div></div></section>

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
<div class="table-wrap"><table><thead><tr><th>状态</th><th>名称</th><th>URL</th><th>模型</th><th>Key</th><th>格式</th><th>能力</th><th>所属池</th><th>准入</th><th>调用</th><th>错误率</th><th>操作</th></tr></thead><tbody id="t-be-list"></tbody></table></div></div>
</div></section>

<section id="panel-retrieval" class="section"><div class="bento"><div class="card full"><h2>检索链路追踪</h2><div class="table-wrap"><table><thead><tr><th>时间</th><th>Query</th><th>命中</th><th>策略</th><th>详情</th></tr></thead><tbody id="t-retrieval"></tbody></table></div></div></div></section>

<section id="panel-model" class="section"><div class="bento">
<div class="card"><h2>路由模型</h2><div class="metric" id="m-name">-</div><div class="metric-label">当前模型</div></div>
<div class="card"><h2>准确率</h2><div class="metric" id="m-accuracy">-</div><div class="metric-label">训练评估</div></div>
<div class="card"><h2>训练数据</h2><div class="metric" id="m-data">0</div><div class="metric-label">样本数</div></div>
<div class="card full"><h2>Fallback 样本与训练 <button class="btn" onclick="triggerRetrain()">触发重训</button></h2><div class="table-wrap"><table><thead><tr><th>时间</th><th>Query</th><th>后端</th><th>原因</th></tr></thead><tbody id="t-fallbacks"></tbody></table></div></div>
</div></section>

<section id="panel-agents" class="section"><div class="bento"><div class="card full"><h2>Agent Task Audit</h2><div class="table-wrap"><table><thead><tr><th>Task</th><th>Status</th><th>Mode</th><th>Repo</th><th>Goal</th><th>Events</th><th>Next</th></tr></thead><tbody id="t-agent-audit"></tbody></table></div></div></div></section>
</main>
</div>
<div class="toast" id="toast"></div>
<script>
const state={stats:null,logs:[],backends:[],model:null,traces:[],agents:[],_poolFilter:'all'};
function authFetch(url,opts={}){opts.headers=Object.assign({'Content-Type':'application/json'},opts.headers||{});opts.credentials='same-origin';return fetch(url,opts)}
function esc(v){return String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
function escJs(v){return String(v??'').replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/\n/g,' ')}
function badge(text,type='off'){return '<span class="badge badge-'+type+'">'+esc(text)+'</span>'}
function fmtUptime(s){s=Number(s||0);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';var d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60);return (d?d+'d ':'')+h+'h '+m+'m'}
function toast(msg,type='ok'){var el=document.getElementById('toast');el.textContent=msg;el.style.borderColor=type==='err'?'rgba(239,68,68,0.5)':'rgba(6,182,212,0.4)';el.classList.add('show');setTimeout(function(){el.classList.remove('show')},4200)}
document.querySelectorAll('#nav button').forEach(function(btn){btn.addEventListener('click',function(){document.querySelectorAll('#nav button').forEach(function(x){x.classList.remove('active')});document.querySelectorAll('.section').forEach(function(x){x.classList.remove('active')});btn.classList.add('active');document.getElementById('panel-'+btn.dataset.panel).classList.add('active')})});
async function json(url,opts){var r=await authFetch(url,opts);if(!r.ok)throw new Error(await r.text());return r.json()}
async function refreshAll(){await Promise.allSettled([loadStats(),loadLogs(),loadBackends(),loadModel(),loadRetrieval(),loadAgents()]);document.getElementById('refresh-info').textContent='刚刚刷新 '+new Date().toLocaleTimeString()}
async function loadStats(){state.stats=await json('/admin/api/stats');renderStats()}
function renderStats(){var d=state.stats||{};document.getElementById('s-total').textContent=d.total_requests??0;document.getElementById('s-avg-ms').textContent=(d.avg_response_ms??0)+'ms';document.getElementById('s-uptime').textContent=fmtUptime(d.uptime_seconds);document.getElementById('s-ips').textContent=d.unique_ips??0;var calls=d.backend_calls||{};document.getElementById('s-backends').textContent=Object.keys(calls).length;var tbody=document.getElementById('t-backends');tbody.innerHTML='';var max=Math.max(1,...Object.values(calls).map(function(x){return Number(x.count||0)}));Object.entries(calls).sort(function(a,b){return(b[1].count||0)-(a[1].count||0)}).slice(0,12).forEach(function(pair){var name=pair[0],info=pair[1];var count=Number(info.count||0),success=Number(info.success||0),rate=count?Math.round(success/count*100):0,avg=count?Math.round(Number(info.total_ms||0)/count):0;tbody.innerHTML+='<tr><td class="mono">'+esc(name)+'</td><td>'+count+'</td><td>'+badge(rate+'%',rate>90?'ok':rate>60?'warn':'err')+'</td><td>'+avg+'</td><td><div class="spark"><span style="width:'+Math.round(count/max*100)+'%"></span></div></td></tr>'});renderIntentTable(d.intent_distribution||{});renderIdeBars(d.ide_distribution||{})}
function renderIntentTable(map){var rows=Object.entries(map).sort(function(a,b){return b[1]-a[1]});var total=rows.reduce(function(a,b){return a+Number(b[1]||0)},0)||1;document.getElementById('t-intents').innerHTML=rows.map(function(pair){return '<tr><td>'+esc(pair[0])+'</td><td>'+pair[1]+'</td><td>'+Math.round(Number(pair[1])/total*100)+'%</td></tr>'}).join('')||'<tr><td colspan="3" class="empty">暂无数据</td></tr>'}
function renderIdeBars(map){var rows=Object.entries(map).sort(function(a,b){return b[1]-a[1]});var max=Math.max(1,...rows.map(function(r){return Number(r[1]||0)}));document.getElementById('ide-bars').innerHTML=rows.map(function(pair){return '<div style="display:grid;grid-template-columns:160px 1fr 50px;gap:10px;align-items:center;margin:10px 0"><span>'+esc(pair[0])+'</span><div class="spark"><span style="width:'+Math.round(Number(pair[1])/max*100)+'%"></span></div><span class="mono">'+pair[1]+'</span></div>'}).join('')||'<div class="empty">暂无数据</div>'}
async function loadLogs(){state.logs=await json('/admin/api/logs');renderLogs()}
function renderLogs(){var q=(document.getElementById('log-filter')?.value||'').toLowerCase();var rows=state.logs.filter(function(l){return JSON.stringify(l).toLowerCase().includes(q)});document.getElementById('t-logs').innerHTML=rows.map(function(l){return '<tr><td class="mini">'+esc(l.time)+'</td><td class="mono">'+esc(l.ip)+'</td><td>'+esc(l.country)+'</td><td>'+esc(l.ide)+'</td><td class="truncate" title="'+esc(l.query||l.sys_prompt)+'">'+esc(l.query||l.sys_prompt)+'</td><td class="mono">'+esc(l.backend)+'</td><td>'+esc(l.intent)+'</td><td>'+esc(l.ms)+'ms</td><td>'+badge(l.success?'成功':'失败',l.success?'ok':'err')+'</td></tr>'}).join('')||'<tr><td colspan="9" class="empty">暂无日志</td></tr>'}
async function loadBackends(){var res=await json('/admin/backends');state.backends=res.backends||[];renderBackends()}
function renderBackends(){var q=(document.getElementById('backend-filter')?.value||'').toLowerCase();var poolFilter=state._poolFilter||'all';var rows=state.backends.filter(function(b){if(poolFilter!=='all'&&(!b.pools||!b.pools.includes(poolFilter)))return false;return JSON.stringify(b).toLowerCase().includes(q)});document.getElementById('t-be-list').innerHTML=rows.map(function(b){var url=b.url||'';var shortUrl=url.length>45?url.substring(0,45)+'...':url;var keyStatus=b.key_configured?badge('已配置','ok'):badge('未配置','err');var caps=(b.caps||[]).slice(0,3).map(function(c){return badge(c,'off')}).join(' ');var pools=(b.pools||[]).map(function(p){return badge(p,p==='code'?'warn':p==='sandbox'?'off':'info')}).join(' ');var adm=b.admission?badge(b.admission,'warn'):'<span class="mini">默认</span>';var enabled=b.in_registry?badge('注册','ok'):badge('未注册','err');return '<tr><td>'+enabled+'</td><td class="mono">'+esc(b.name)+'</td><td class="truncate" title="'+esc(url)+'">'+esc(shortUrl)+'</td><td>'+esc(b.model)+'</td><td>'+keyStatus+'</td><td>'+esc(b.fmt)+'</td><td>'+caps+'</td><td>'+pools+'</td><td>'+adm+'</td><td>'+esc(b.total_calls||0)+'</td><td>'+esc(b.error_rate||'0%')+'</td><td><button class="btn ghost" onclick="editBackend(\''+escJs(b.name)+'\')">编辑</button> <button class="btn ghost" onclick="testBackend(\''+escJs(b.name)+'\')">测试</button> <button class="btn danger" onclick="deleteBackend(\''+escJs(b.name)+'\')">删除</button></td></tr>'}).join('')||'<tr><td colspan="12" class="empty">暂无后端</td></tr>'}
function filterPool(pool){state._poolFilter=pool;document.querySelectorAll('.filter-bar button').forEach(function(btn){btn.classList.remove('active')});var el=document.getElementById('pool-'+pool);if(el)el.classList.add('active');renderBackends()}
async function addBackend(){var body={name:v('be-name'),url:v('be-url'),model:v('be-model'),key:v('be-key'),fmt:v('be-fmt'),auth:v('be-auth'),tier:v('be-tier'),admission:v('be-admission')};try{var res=await json('/admin/backends',{method:'POST',body:JSON.stringify(body)});toast(res.message||'已添加');await loadBackends()}catch(e){toast('添加失败：'+e.message,'err')}}
async function testBackend(name){try{var res=await json('/admin/backends/'+encodeURIComponent(name)+'/test',{method:'POST'});toast(name+' 测试 '+((res.ok?'通过':'失败')+' '+(res.latency_ms||0)+'ms'),res.ok?'ok':'err')}catch(e){toast('测试失败：'+e.message,'err')}}
async function deleteBackend(name){if(!confirm('删除后端 '+name+' ?'))return;try{await json('/admin/backends/'+encodeURIComponent(name),{method:'DELETE'});toast('已删除 '+name);await loadBackends()}catch(e){toast('删除失败：'+e.message,'err')}}
function editBackend(name){var b=state.backends.find(function(x){return x.name===name});if(!b){toast('后端不存在','err');return}var newUrl=prompt('API URL',b.url||'');if(newUrl===null)return;var newModel=prompt('模型名称',b.model||'');if(newModel===null)return;var newCaps=prompt('能力 (逗号分隔)',(b.caps||[]).join(','));if(newCaps===null)return;var newAdm=prompt('准入策略 (空=默认, code_medium_candidate=编程池, sandbox_only=沙箱)',b.admission||'');if(newAdm===null)return;var body={url:newUrl,model:newModel,caps:newCaps.split(',').filter(function(x){return x.trim()}),admission:newAdm};json('/admin/backends/'+encodeURIComponent(name),{method:'PUT',body:JSON.stringify(body)}).then(function(){toast('已更新 '+name);loadBackends()}).catch(function(e){toast('更新失败: '+e.message,'err')})}
function v(id){return document.getElementById(id).value.trim()}
async function loadModel(){state.model=await json('/admin/api/model-status');renderModel()}
function renderModel(){var d=state.model||{};document.getElementById('m-name').textContent=d.model||'-';document.getElementById('m-accuracy').textContent=d.accuracy||'-';document.getElementById('m-data').textContent=d.data_count||0;document.getElementById('s-fallbacks').textContent=d.fallback_log_count||0;var rows=d.recent_fallbacks||[];document.getElementById('t-fallbacks').innerHTML=rows.slice().reverse().map(function(x){return '<tr><td>'+esc(x.time||x.ts||'')+'</td><td class="truncate">'+esc(x.query||x.prompt||'')+'</td><td class="mono">'+esc(x.backend||'')+'</td><td>'+esc(x.reason||x.error||'')+'</td></tr>'}).join('')||'<tr><td colspan="4" class="empty">暂无 fallback</td></tr>'}
async function triggerRetrain(){if(!confirm('确认触发 auto_retrain.py --force ?'))return;try{var r=await json('/admin/api/retrain',{method:'POST'});toast('训练任务：'+(r.job_id||r.status))}catch(e){toast('触发失败：'+e.message,'err')}}
async function loadRetrieval(){state.traces=await json('/admin/api/retrieval-traces');renderRetrieval()}
function renderRetrieval(){var rows=Array.isArray(state.traces)?state.traces:[];document.getElementById('t-retrieval').innerHTML=rows.map(function(t){return '<tr><td>'+esc(t.time||t.ts||'')+'</td><td class="truncate">'+esc(t.query||'')+'</td><td>'+esc(t.hits??t.hit_count??'')+'</td><td>'+esc(t.strategy||t.mode||'')+'</td><td class="truncate" title="'+esc(JSON.stringify(t))+'">'+esc(JSON.stringify(t))+'</td></tr>'}).join('')||'<tr><td colspan="5" class="empty">暂无检索追踪</td></tr>'}
async function loadAgents(){var d=await json('/admin/api/agent-audit?limit=50');state.agents=d.tasks||[];renderAgents()}
function renderAgents(){document.getElementById('t-agent-audit').innerHTML=state.agents.map(function(t){return '<tr><td class="mono">'+esc(t.task_id||t.id)+'</td><td>'+badge(t.status||'-',String(t.status).includes('fail')?'err':String(t.status).includes('review')?'warn':'ok')+'</td><td>'+esc(t.mode)+'</td><td class="truncate">'+esc(t.repo)+'</td><td class="truncate" title="'+esc(t.goal)+'">'+esc(t.goal)+'</td><td>'+esc(t.events_count??t.event_count??'')+'</td><td>'+esc(t.next_action||'')+'</td></tr>'}).join('')||'<tr><td colspan="7" class="empty">暂无 Agent 任务</td></tr>'}
refreshAll();setInterval(refreshAll,5000);
</script>
</body>
</html>'''

LOGIN_HTML = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>&#x674e;&#x9a6c;&#x7ba1;&#x7406;&#x9762;&#x677f; - &#x767b;&#x5f55;</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 20% 0%,rgba(53,213,255,.2),transparent 30%),#07111f;color:#e8f1ff;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.card{width:min(420px,calc(100% - 32px));padding:30px;border:1px solid rgba(145,166,210,.2);border-radius:28px;background:rgba(15,27,50,.88);box-shadow:0 18px 55px rgba(0,0,0,.38)}h1{margin:0 0 8px}.muted{color:#8fa3c7}input{width:100%;box-sizing:border-box;margin:18px 0 12px;border:1px solid rgba(145,166,210,.22);border-radius:14px;background:#07111f;color:#e8f1ff;padding:13px}button{width:100%;border:0;border-radius:14px;background:linear-gradient(135deg,#35d5ff,#a78bfa);color:#07111f;font-weight:900;padding:12px;cursor:pointer}.err{color:#fecdd3;background:rgba(251,113,133,.13);border:1px solid rgba(251,113,133,.28);padding:10px;border-radius:12px;margin-bottom:12px}</style></head><body><form class="card" method="post" action="/admin/login"><h1>&#x674e;&#x9a6c;&#x7ba1;&#x7406;&#x9762;&#x677f;</h1><p class="muted">&#x8f93;&#x5165;&#x7ba1;&#x7406;&#x5458; Token &#x8fdb;&#x5165;&#x751f;&#x4ea7;&#x63a7;&#x5236;&#x53f0;&#x3002;</p>{error}<input name="token" placeholder="Admin Token" type="password" autofocus><button type="submit">&#x767b;&#x5f55;</button></form></body></html>'

def render_admin_login(error: str = "") -> str:
    error_html = '<p class="err">' + error + '</p>' if error else ""
    return LOGIN_HTML.replace("{error}", error_html)


def render_admin_dashboard() -> str:
    return ADMIN_HTML
