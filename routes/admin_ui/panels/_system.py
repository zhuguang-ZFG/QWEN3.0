"""System panels: config import/export, devices, alerts, live logs."""

CONFIG = """\
<section id="panel-config" class="section">
  <div class="card">
    <h2>配置导出</h2>
    <p class="mini">版本: <span id="cfg-version" class="mono">-</span></p>
    <pre id="cfg-preview" style="background:rgba(8,12,20,0.6);border:1px solid var(--line);border-radius:12px;padding:12px;font-size:12px;max-height:300px;overflow:auto;margin:12px 0"></pre>
    <button class="btn" onclick="exportConfig()">导出配置</button>
  </div>
  <div class="card">
    <h2>配置导入</h2>
    <input type="file" id="config-file" accept=".json" style="margin:12px 0">
    <br><button class="btn" onclick="importConfig()">导入配置</button>
  </div>
</section>
"""

DEVICES = """\
<section id="panel-devices" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="dev-total">0</div><div class="metric-label">在线设备</div></div>
    <div class="card"><div class="metric" style="color:var(--cyan)" id="dev-tasks">0</div><div class="metric-label">待处理任务</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>设备列表</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>设备 ID</th><th>固件</th><th>能力</th><th>运行时间</th><th>任务数</th><th>操作</th></tr></thead>
      <tbody id="t-devices"></tbody>
    </table></div>
  </div>
</section>
"""

ALERTS = """\
<section id="panel-alerts" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="alert-total">0</div><div class="metric-label">总规则数</div></div>
    <div class="card"><div class="metric" style="color:var(--green)" id="alert-active">0</div><div class="metric-label">启用中</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>告警规则
      <button class="btn" onclick="showAddAlert()">+ 添加规则</button>
    </h2>
    <div id="alert-add-form" style="display:none;margin-bottom:16px;padding:16px;border:1px solid var(--line);border-radius:16px">
      <div class="form">
        <input id="al-name" placeholder="规则名称">
        <select id="al-metric"><option value="error_rate">错误率</option><option value="latency_ms">延迟</option><option value="fallback_rate">Fallback率</option><option value="request_count">请求量</option></select>
        <select id="al-condition"><option value="gt">大于</option><option value="lt">小于</option><option value="eq">等于</option></select>
        <input id="al-threshold" type="number" placeholder="阈值" step="0.01">
        <input id="al-window" type="number" placeholder="窗口(秒)" value="300">
        <button class="btn" onclick="addAlertRule()">创建</button>
      </div>
      <button class="btn ghost" onclick="hideAddAlert()" style="margin-top:8px">取消</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>名称</th><th>指标</th><th>条件</th><th>阈值</th><th>窗口</th><th>状态</th><th>操作</th></tr></thead>
      <tbody id="t-alerts"></tbody>
    </table></div>
  </div>
</section>
"""

LIVE_LOGS = """\
<section id="panel-live-logs" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="ll-count">0</div><div class="metric-label">接收条数</div></div>
    <div class="card"><div class="metric" style="color:var(--green)" id="ll-success">0</div><div class="metric-label">成功</div></div>
    <div class="card"><div class="metric" style="color:var(--red)" id="ll-fail">0</div><div class="metric-label">失败</div></div>
    <div class="card">
      <span class="mini">状态: </span><span id="ll-status" class="mono">未连接</span>
      <div style="margin-top:10px">
        <button class="btn" id="ll-toggle" onclick="toggleLiveLogs()">开始监听</button>
        <button class="btn ghost" onclick="clearLiveLogs()">清空</button>
      </div>
    </div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>实时日志流
      <input class="search" id="ll-filter" placeholder="过滤..." oninput="filterLiveLogs()" style="max-width:200px">
    </h2>
    <div class="table-wrap"><table>
      <thead><tr><th>时间</th><th>IP</th><th>国家</th><th>IDE</th><th>查询</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead>
      <tbody id="t-live-logs"></tbody>
    </table></div>
  </div>
</section>
"""
