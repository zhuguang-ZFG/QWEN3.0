"""routes/admin.py — LiMa 管理接口"""
import os
import sys
import json
import time
import hashlib
import hmac
import secrets
import threading
import subprocess
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

import smart_router

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

_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")
_SESSION_COOKIE = "lima_admin_session"


def _admin_session_value() -> str:
    return hmac.new(
        _ADMIN_TOKEN.encode("utf-8"),
        b"lima-admin-session",
        hashlib.sha256,
    ).hexdigest()


def _is_valid_admin_session(value: str) -> bool:
    return bool(
        _ADMIN_TOKEN
        and value
        and secrets.compare_digest(value, _admin_session_value())
    )


async def _verify_admin(
    authorization: str = Header(default=""),
    lima_admin_session: str = Cookie(default=""),
) -> None:
    """管理接口认证。需设置 LIMA_ADMIN_TOKEN 环境变量。"""
    if not _ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="LiMa admin token is not configured.",
        )
    if _is_valid_admin_session(lima_admin_session):
        return
    if authorization != f"Bearer {_ADMIN_TOKEN}" and authorization != _ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Stats / Logs ───────────────────────────────────────────────────────────────

@router.get("/api/stats", dependencies=[Depends(_verify_admin)])
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


@router.get("/api/logs", dependencies=[Depends(_verify_admin)])
async def admin_logs():
    """返回最近请求日志。"""
    with _stats_lock:
        return list(reversed(_stats["recent_logs"][-10:]))


@router.get("/api/retrieval-traces", dependencies=[Depends(_verify_admin)])
async def admin_retrieval_traces():
    """返回最近的 retrieval injection 追踪记录。"""
    try:
        from context_pipeline.retrieval_trace import get_recent_traces
        return get_recent_traces(limit=20)
    except ImportError:
        return []


@router.get("/api/agent-audit", dependencies=[Depends(_verify_admin)])
async def admin_agent_audit(limit: int = 20):
    from routes.agent_tasks import _store, _task_audit_item
    safe_limit = max(1, min(int(limit), 100))
    tasks = list(_store.values())
    tasks.sort(
        key=lambda t: t.get("updated_at", t.get("created_at", 0)),
        reverse=True,
    )
    items = [_task_audit_item(task) for task in tasks[:safe_limit]]
    return {"tasks": items, "count": len(items)}


# ── Backends ───────────────────────────────────────────────────────────────────

@router.get("/api/backends", dependencies=[Depends(_verify_admin)])
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


@router.post("/api/backends", dependencies=[Depends(_verify_admin)])
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


@router.delete("/api/backends/{name}", dependencies=[Depends(_verify_admin)])
async def admin_delete_backend(name: str):
    """删除后端。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    del smart_router.BACKENDS[name]
    _backend_enabled.pop(name, None)
    return {"ok": True, "message": f"backend '{name}' deleted"}


@router.post("/api/backends/{name}/toggle", dependencies=[Depends(_verify_admin)])
async def admin_toggle_backend(name: str):
    """启用/禁用后端。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    current = _backend_enabled.get(name, True)
    _backend_enabled[name] = not current
    return {"ok": True, "enabled": not current}


@router.post("/api/backends/{name}/test", dependencies=[Depends(_verify_admin)])
async def admin_test_backend(name: str):
    """测试后端可用性：发送简单请求验证连通性。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    return _test_backend_sync(name)


# ── Model status / retrain ─────────────────────────────────────────────────────

@router.get("/api/model-status", dependencies=[Depends(_verify_admin)])
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


@router.post("/api/retrain", dependencies=[Depends(_verify_admin)])
async def admin_trigger_retrain():
    """手动触发自动训练。"""
    result = subprocess.run(
        [sys.executable, "auto_retrain.py", "--force"],
        capture_output=True, text=True, cwd="D:/GIT"
    )
    return {"status": "triggered", "output": result.stdout[-500:] if result.stdout else result.stderr[-500:]}


# ── Admin HTML ─────────────────────────────────────────────────────────────────

ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LiMa - 管理后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:20px}
h1{color:#00d4ff;margin-bottom:20px;font-size:1.6em}
h2{color:#00d4ff;margin-bottom:12px;font-size:1.1em;border-bottom:1px solid #2a2a4e;padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:24px}
.card{background:#16213e;border-radius:10px;padding:18px;border:1px solid #2a2a4e}
.stat-num{font-size:2em;font-weight:700;color:#00d4ff}
.stat-label{font-size:0.85em;color:#888;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:0.85em}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #2a2a4e}
th{color:#00d4ff;font-weight:600}
tr:hover{background:#1f2b47}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:600}
.badge-ok{background:#0d4d2e;color:#4caf50}
.badge-err{background:#4d0d0d;color:#f44336}
.badge-off{background:#3d3d3d;color:#999}
button{background:#00d4ff;color:#1a1a2e;border:none;padding:6px 14px;border-radius:5px;cursor:pointer;font-size:0.8em;font-weight:600}
button:hover{background:#00b8d4}
button.danger{background:#f44336;color:#fff}
button.danger:hover{background:#d32f2f}
input,select{background:#0f1a30;border:1px solid #2a2a4e;color:#e0e0e0;padding:6px 10px;border-radius:5px;font-size:0.85em}
input:focus,select:focus{outline:none;border-color:#00d4ff}
.form-row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center}
.form-row input{flex:1;min-width:120px}
.log-time{color:#888;font-size:0.8em}
.log-backend{color:#00d4ff}
.log-query{color:#ccc;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tabs{display:flex;gap:4px;margin-bottom:16px}
.tab{padding:8px 18px;background:#16213e;border:1px solid #2a2a4e;border-radius:6px 6px 0 0;cursor:pointer;color:#888}
.tab.active{background:#1f2b47;color:#00d4ff;border-bottom-color:#1f2b47}
.panel{display:none}
.panel.active{display:block}
.refresh-info{font-size:0.75em;color:#555;margin-left:12px}
</style>
</head>"""

ADMIN_BODY = """<body>
<h1>LiMa 管理后台<span class="refresh-info" id="refresh-info">每5秒自动刷新</span></h1>
<div class="tabs">
  <div class="tab active" onclick="switchTab('stats')">实时指标</div>
  <div class="tab" onclick="switchTab('backends')">后端管理</div>
  <div class="tab" onclick="switchTab('model')">模型 & Fallback</div>
  <div class="tab" onclick="switchTab('agents')">Agent Tasks</div>
</div>

<div id="panel-stats" class="panel active">
  <div class="grid">
    <div class="card"><div class="stat-num" id="s-total">0</div><div class="stat-label">总请求数</div></div>
    <div class="card"><div class="stat-num" id="s-avg-ms">0ms</div><div class="stat-label">平均响应时间</div></div>
    <div class="card"><div class="stat-num" id="s-uptime">0s</div><div class="stat-label">运行时间</div></div>
    <div class="card"><div class="stat-num" id="s-backends">0</div><div class="stat-label">活跃后端</div></div>
    <div class="card"><div class="stat-num" id="s-ips">0</div><div class="stat-label">活跃用户(IP)</div></div>
  </div>
  <div class="grid">
    <div class="card"><h2>后端调用统计</h2><table><thead><tr><th>后端</th><th>调用</th><th>成功率</th><th>平均ms</th></tr></thead><tbody id="t-backends"></tbody></table></div>
    <div class="card"><h2>意图分布</h2><table><thead><tr><th>意图</th><th>次数</th><th>占比</th></tr></thead><tbody id="t-intents"></tbody></table></div>
    <div class="card"><h2>IDE 分布</h2><table><thead><tr><th>IDE</th><th>次数</th></tr></thead><tbody id="t-ides"></tbody></table></div>
  </div>
  <div class="card" style="margin-top:16px"><h2>最近请求日志</h2><table><thead><tr><th>时间</th><th>IP</th><th>国家</th><th>IDE</th><th>查询</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead><tbody id="t-logs"></tbody></table></div>
</div>

<div id="panel-backends" class="panel">
  <div class="card" style="margin-bottom:16px">
    <h2>添加新后端</h2>
    <div class="form-row">
      <input id="nb-name" placeholder="名称" style="flex:1">
      <input id="nb-url" placeholder="API URL" style="flex:2">
      <select id="nb-fmt"><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select>
      <select id="nb-tier"><option value="">自动检测</option><option value="L0">L0 本地</option><option value="L1">L1 免费无限</option><option value="L2">L2 免费额度</option><option value="L3">L3 免费限量</option><option value="L4">L4 付费</option></select>
    </div>
    <div class="form-row" style="margin-top:6px">
      <input id="nb-key" placeholder="API Key (可选)" style="flex:2">
      <input id="nb-model" placeholder="模型名" style="flex:2">
      <input id="nb-auth" placeholder="认证方式 (默认x-api-key)" style="flex:1">
    </div>
    <div class="form-row" style="margin-top:6px">
      <input id="nb-caps" placeholder="能力标签(逗号分隔,如: 工具调用,视觉,深度推理)" style="flex:3">
      <button onclick="addBackend()" style="flex:1">添加并测试</button>
    </div>
  </div>
  <div class="card"><h2>后端列表</h2><table><thead><tr><th>名称</th><th>供应商</th><th>层级</th><th>协议</th><th>能力</th><th>模型</th><th>URL</th><th>状态</th><th>测试</th><th>操作</th></tr></thead><tbody id="t-be-list"></tbody></table></div>
</div>

<div id="panel-model" class="panel">
  <div class="grid">
    <div class="card">
      <h2>路由模型状态</h2>
      <table>
        <tr><td>当前模型</td><td id="m-model">-</td></tr>
        <tr><td>准确率</td><td id="m-accuracy">-</td></tr>
        <tr><td>数据量</td><td id="m-data">-</td></tr>
        <tr><td>Fallback 率</td><td id="m-fallback-rate">-</td></tr>
      </table>
    </div>
    <div class="card">
      <h2>自动训练状态</h2>
      <table>
        <tr><td>Fallback 日志</td><td id="m-log-count">0 / 100</td></tr>
        <tr><td>下次训练触发</td><td id="m-next-train">日志满100条</td></tr>
        <tr><td>上次训练</td><td id="m-last-train">-</td></tr>
      </table>
      <button onclick="triggerRetrain()" style="margin-top:10px">手动触发训练</button>
    </div>
  </div>
  <div class="card" style="margin-top:16px">
    <h2>Fallback 日志（最近50条）</h2>
    <table>
      <thead><tr><th>时间</th><th>查询</th><th>原后端</th><th>Fallback到</th><th>IDE</th><th>意图</th></tr></thead>
      <tbody id="t-fallback-logs"></tbody>
    </table>
  </div>
</div>

<div id="panel-agents" class="panel">
  <div class="card">
    <h2>Agent Task Audit</h2>
    <table>
      <thead><tr><th>Task</th><th>Status</th><th>Mode</th><th>Repo</th><th>Goal</th><th>Events</th><th>Next</th></tr></thead>
      <tbody id="t-agent-audit"></tbody>
    </table>
  </div>
</div>"""

ADMIN_JS = """<script>
function authFetch(url,opts={}){
  opts.headers=Object.assign({},opts.headers||{});
  opts.credentials='same-origin';
  return fetch(url,opts);
}
function switchTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('panel-'+name).classList.add('active');
}
function fmtUptime(s){
  if(s<60)return s+'s';
  if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';
  let h=Math.floor(s/3600),m=Math.floor((s%3600)/60);
  return h+'h '+m+'m';
}
async function loadStats(){
  try{
    let r=await authFetch('/admin/api/stats');let d=await r.json();
    document.getElementById('s-total').textContent=d.total_requests;
    document.getElementById('s-avg-ms').textContent=d.avg_response_ms+'ms';
    document.getElementById('s-uptime').textContent=fmtUptime(d.uptime_seconds);
    document.getElementById('s-backends').textContent=Object.keys(d.backend_calls).length;
    document.getElementById('s-ips').textContent=d.unique_ips||0;
    let tb=document.getElementById('t-backends');tb.innerHTML='';
    for(let[name,info]of Object.entries(d.backend_calls)){
      let rate=info.count>0?Math.round(info.success/info.count*100):0;
      let avg=info.count>0?Math.round(info.total_ms/info.count):0;
      tb.innerHTML+=`<tr><td>${name}</td><td>${info.count}</td><td><span class="badge ${rate>90?'badge-ok':'badge-err'}">${rate}%</span></td><td>${avg}</td></tr>`;
    }
    let ti=document.getElementById('t-intents');ti.innerHTML='';
    let total=Object.values(d.intent_distribution).reduce((a,b)=>a+b,0)||1;
    let sorted=Object.entries(d.intent_distribution).sort((a,b)=>b[1]-a[1]);
    for(let[intent,count]of sorted){
      ti.innerHTML+=`<tr><td>${intent}</td><td>${count}</td><td>${Math.round(count/total*100)}%</td></tr>`;
    }
    let tIde=document.getElementById('t-ides');tIde.innerHTML='';
    if(d.ide_distribution){
      let ideSorted=Object.entries(d.ide_distribution).sort((a,b)=>b[1]-a[1]);
      for(let[ide,count]of ideSorted){
        tIde.innerHTML+=`<tr><td>${ide}</td><td>${count}</td></tr>`;
      }
    }
  }catch(e){console.error('stats error',e)}
}
function esc(s){return s?s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):''}
async function loadLogs(){
  try{
    let r=await authFetch('/admin/api/logs');let d=await r.json();
    let tl=document.getElementById('t-logs');tl.innerHTML='';
    for(let log of d){
      let cls=log.success?'badge-ok':'badge-err';
      tl.innerHTML+=`<tr><td class="log-time">${esc(log.time)}</td><td style="font-size:11px">${esc(log.ip||'')}</td><td>${esc(log.country||'')}</td><td>${esc(log.ide||'')}</td><td class="log-query" title="${esc(log.sys_prompt||'')}">${esc(log.query)}</td><td class="log-backend">${esc(log.backend)}</td><td>${esc(log.intent)}</td><td>${log.ms}ms</td><td><span class="badge ${cls}">${log.success?'OK':'ERR'}</span></td></tr>`;
    }
  }catch(e){console.error('logs error',e)}
}
async function loadBackends(){
  try{
    let r=await authFetch('/admin/api/backends');let d=await r.json();
    let tb=document.getElementById('t-be-list');tb.innerHTML='';
    for(let b of d){
      let stCls=b.enabled?'badge-ok':'badge-off';
      let stTxt=b.enabled?'启用':'禁用';
      let cbCls=b.state==='open'?'badge-err':'badge-ok';
      let caps=(b.capabilities||[]).map(c=>`<span class="badge ${c.includes('工具')?'badge-ok':c.includes('推理')?'badge-off':''}" style="font-size:10px;margin:1px">${c}</span>`).join('');
      let urlShort=(b.url||'').length>30?b.url.substring(0,30)+'...':(b.url||'');
      tb.innerHTML+=`<tr><td>${b.name}</td><td>${b.vendor||''}</td><td><span class="badge ${b.tier&&b.tier.includes('免费')?'badge-ok':b.tier&&b.tier.includes('付费')?'badge-err':'badge-off'}">${b.tier||''}</span></td><td>${b.protocol||''}</td><td>${caps}</td><td style="font-size:11px">${b.model}</td><td style="font-size:10px;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(b.url||'').replace(/"/g,'&quot;')}">${urlShort}</td><td><span class="badge ${stCls}">${stTxt}</span></td><td><button onclick="testBackend('${b.name}')">测试</button> <button onclick="toggleBackend('${b.name}')">${b.enabled?'禁用':'启用'}</button> <button class="danger" onclick="deleteBackend('${b.name}')">删除</button></td></tr>`;
    }
  }catch(e){console.error('backends error',e)}
}
async function loadModelStatus(){
  try{
    let r=await authFetch('/admin/api/model-status');let d=await r.json();
    document.getElementById('m-model').textContent=d.model||'-';
    document.getElementById('m-accuracy').textContent=d.accuracy||'-';
    document.getElementById('m-data').textContent=(d.data_count||0)+' 条';
    let fbRate=d.fallback_log_count>0?Math.round(d.fallback_log_count/Math.max(1,d.data_count)*100)+'%':'-';
    document.getElementById('m-fallback-rate').textContent=fbRate;
    document.getElementById('m-log-count').textContent=d.fallback_log_count+' / '+d.threshold;
    document.getElementById('m-next-train').textContent=d.fallback_log_count>=d.threshold?'已就绪，可触发':'日志满'+d.threshold+'条';
    document.getElementById('m-last-train').textContent=d.model||'-';
    let tb=document.getElementById('t-fallback-logs');tb.innerHTML='';
    for(let log of (d.recent_fallbacks||[])){
      tb.innerHTML+=`<tr><td class="log-time">${esc(log.timestamp||'')}</td><td class="log-query">${esc((log.query||'').substring(0,60))}</td><td>${esc(log.original_backend||'')}</td><td class="log-backend">${esc(log.fallback_backend||'')}</td><td>${esc(log.ide||'')}</td><td>${esc(log.intent||'')}</td></tr>`;
    }
  }catch(e){console.error('model-status error',e)}
}
async function triggerRetrain(){
  if(!confirm('确定手动触发训练？'))return;
  try{
    let r=await authFetch('/admin/api/retrain',{method:'POST'});
    let d=await r.json();
    alert('训练触发: '+d.status+'\\n'+((d.output||'').substring(0,300)));
    loadModelStatus();
  }catch(e){alert('触发失败: '+e)}
}
async function addBackend(){
  let name=document.getElementById('nb-name').value.trim();
  let url=document.getElementById('nb-url').value.trim();
  let key=document.getElementById('nb-key').value.trim();
  let model=document.getElementById('nb-model').value.trim();
  let fmt=document.getElementById('nb-fmt').value;
  let tier=document.getElementById('nb-tier').value;
  let auth=document.getElementById('nb-auth').value.trim();
  let capsRaw=document.getElementById('nb-caps').value.trim();
  let caps=capsRaw?capsRaw.split(',').map(s=>s.trim()).filter(s=>s):[];
  if(!name||!url){alert('名称和URL必填');return}
  let r=await authFetch('/admin/api/backends',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,url,key,model:model||name,fmt,tier,auth,caps})});
  let d=await r.json();
  if(r.ok){
    document.getElementById('nb-name').value='';document.getElementById('nb-url').value='';document.getElementById('nb-key').value='';document.getElementById('nb-model').value='';document.getElementById('nb-auth').value='';document.getElementById('nb-caps').value='';
    loadBackends();
    if(d.test){alert(d.test.ok?`✅ 添加成功\n测试延迟: ${d.test.latency_ms}ms\n响应: ${d.test.response_preview||''}`:`⚠️ 添加成功但测试失败\n错误: ${d.test.error||''}`)}
    else{alert(d.message||'添加成功')}
  }else{alert(d.detail||'添加失败')}
}
async function deleteBackend(name){
  if(!confirm('确定删除后端 '+name+' ?'))return;
  await authFetch('/admin/api/backends/'+name,{method:'DELETE'});loadBackends();
}
async function toggleBackend(name){
  await authFetch('/admin/api/backends/'+name+'/toggle',{method:'POST'});loadBackends();
}
async function testBackend(name){
  let btn=event.target;btn.disabled=true;btn.textContent='测试中...';
  try{
    let r=await authFetch('/admin/api/backends/'+name+'/test',{method:'POST'});
    let d=await r.json();
    if(d.ok){alert(`✅ ${name} 可用\\n延迟: ${d.latency_ms}ms\\n响应: ${d.response_preview||''}`)}
    else{alert(`❌ ${name} 不可用\\n延迟: ${d.latency_ms}ms\\n错误: ${d.error||''}`)}
  }catch(e){alert('测试失败: '+e)}
  btn.disabled=false;btn.textContent='测试';loadBackends();
}
async function loadAgentAudit(){
  try{
    let r=await authFetch('/admin/api/agent-audit?limit=20');let d=await r.json();
    let tb=document.getElementById('t-agent-audit');if(!tb)return;tb.innerHTML='';
    for(let task of (d.tasks||[])){
      tb.innerHTML+=`<tr><td>${esc(task.task_id)}</td><td>${esc(task.status)}</td><td>${esc(task.mode)}</td><td>${esc(task.repo)}</td><td>${esc(task.goal)}</td><td>${task.event_count}</td><td>${esc(task.next_action||'')}</td></tr>`;
    }
  }catch(e){console.error('agent audit error',e)}
}
function refreshAll(){loadStats();loadLogs();loadBackends();loadModelStatus();loadAgentAudit()}
refreshAll();
setInterval(refreshAll,5000);
</script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse)
async def admin_page(
    lima_admin_session: str = Cookie(default=""),
):
    """管理后台 Web UI。仅支持 HttpOnly session cookie 访问。"""
    if not _ADMIN_TOKEN:
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    authenticated = _is_valid_admin_session(lima_admin_session)
    if not authenticated:
        return HTMLResponse(
            "<h2>Admin Login</h2>"
            '<form method="post" action="/admin/login">'
            '<input name="token" placeholder="Admin Token" type="password">'
            '<button type="submit">Login</button></form>',
            status_code=401,
        )
    return HTMLResponse(ADMIN_HTML + ADMIN_BODY + ADMIN_JS)


@router.post("/login")
async def admin_login(request: Request):
    """POST 登录，设置 httponly cookie。"""
    form = await request.form()
    token = form.get("token", "")
    if token != _ADMIN_TOKEN:
        return HTMLResponse(
            "<h2>Admin Login</h2><p style='color:red'>Token 错误</p>"
            '<form method="post" action="/admin/login">'
            '<input name="token" placeholder="Admin Token" type="password">'
            '<button type="submit">Login</button></form>',
            status_code=401,
        )
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        _SESSION_COOKIE,
        _admin_session_value(),
        httponly=True, secure=True, samesite="strict", max_age=86400,
    )
    return response


@router.get("/logout")
async def admin_logout():
    """清除 cookie 并跳转登录页。"""
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie(_SESSION_COOKIE, secure=True, samesite="strict")
    return response
