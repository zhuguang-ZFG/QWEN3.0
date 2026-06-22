"""Admin UI panel HTML templates — aggregated dashboard panels.

Consolidated from routes/admin_ui/panels/ (13 files / 14 panels) into a single
module during round 4 slimming. Each panel is a zero-logic HTML string constant.
"""

OVERVIEW = """\
<section id="panel-overview" class="section active">
  <div class="bento">
    <div class="card"><div class="metric" id="s-total">0</div><div class="metric-label">总请求数</div></div>
    <div class="card"><div class="metric" id="s-avg-ms">0ms</div><div class="metric-label">平均响应时间</div></div>
    <div class="card"><div class="metric" id="s-uptime">0s</div><div class="metric-label">运行时间</div></div>
    <div class="card"><div class="metric" id="s-ips">0</div><div class="metric-label">活跃 IP</div></div>
    <div class="card"><div class="metric" id="s-backends">0</div><div class="metric-label">活跃后端</div></div>
    <div class="card"><div class="metric mini" id="s-time" style="font-size:14px;padding-top:14px"></div><div class="metric-label">最后刷新</div></div>
  </div>
  <div class="bento" style="margin-top:18px">
    <div class="card wide">
      <h2>后端调用统计 <span class="mini" id="s-git"></span></h2>
      <div class="table-wrap"><table>
        <thead><tr><th>后端</th><th>调用</th><th>成功率</th><th>均耗ms</th><th>占比</th></tr></thead>
        <tbody id="t-backends"></tbody>
      </table></div>
    </div>
    <div class="card">
      <h2>意图分布</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>意图</th><th>次数</th><th>占比</th></tr></thead>
        <tbody id="t-intents"></tbody>
      </table></div>
    </div>
  </div>
  <div class="bento" style="margin-top:18px">
    <div class="card full">
      <h2>IDE 分布</h2>
      <div id="ide-bars"></div>
    </div>
  </div>
  <span class="mini" id="s-py" style="display:none"></span>
</section>
"""

TRAFFIC = """\
<section id="panel-traffic" class="section">
  <div class="card full">
    <h2>最近请求日志
      <div class="toolbar">
        <input class="search" id="log-filter" placeholder="搜索日志..." oninput="renderLogs()" style="max-width:240px">
        <button class="btn ghost" onclick="exportLogsCSV()">导出 CSV</button>
        <button class="btn ghost" onclick="exportLogsJSON()">导出 JSON</button>
      </div>
    </h2>
    <div class="table-wrap"><table>
      <thead><tr><th>时间</th><th>IP</th><th>国家</th><th>IDE</th><th>查询</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead>
      <tbody id="t-logs"></tbody>
    </table></div>
  </div>
</section>
"""

BACKENDS = """\
<section id="panel-backends" class="section">
  <div class="card full">
    <h2>后端列表
      <div class="toolbar">
        <input class="search" id="backend-filter" placeholder="搜索后端..." oninput="renderBackends()" style="max-width:200px">
      </div>
    </h2>
    <div class="filter-bar">
      <button class="btn active" id="pool-all" onclick="filterPool('all')">全部</button>
      <button class="btn" id="pool-code" onclick="filterPool('code')">Code</button>
      <button class="btn" id="pool-sandbox" onclick="filterPool('sandbox')">Sandbox</button>
      <button class="btn" id="pool-general" onclick="filterPool('general')">General</button>
    </div>
    <div id="batch-bar" style="display:none;margin-bottom:12px">
      <span id="batch-count" class="mini"></span>
      <button class="btn" onclick="batchTest()">批量测试</button>
      <button class="btn danger" onclick="batchDisable()">批量删除</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr>
        <th><input type="checkbox" onchange="toggleSelectAll(this)"></th>
        <th>注册</th><th>名称</th><th>URL</th><th>模型</th><th>Key</th>
        <th>协议</th><th>能力</th><th>池</th><th>准入</th>
        <th>调用</th><th>错误率</th><th>操作</th>
      </tr></thead>
      <tbody id="t-be-list"></tbody>
    </table></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>添加新后端</h2>
    <div class="form">
      <input id="be-name" placeholder="名称 *">
      <input id="be-url" class="span2" placeholder="API URL">
      <input id="be-model" placeholder="模型名">
      <input id="be-key" placeholder="API Key">
      <select id="be-fmt"><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select>
      <input id="be-auth" placeholder="认证方式">
      <select id="be-tier"><option value="">自动检测</option><option value="L1">L1 免费无限</option><option value="L2">L2 免费额度</option><option value="L3">L3 免费限量</option><option value="L4">L4 付费</option></select>
      <input id="be-admission" placeholder="准入策略" class="span2">
      <button class="btn" onclick="addBackend()">添加</button>
    </div>
  </div>
</section>
"""

RETRIEVAL = """\
<section id="panel-retrieval" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="r-count">0</div><div class="metric-label">追踪条数</div></div>
    <div class="card"><div class="metric" id="r-avg-cand">0</div><div class="metric-label">平均候选数</div></div>
    <div class="card"><div class="metric" id="r-avg-prec">0%</div><div class="metric-label">平均精度</div></div>
    <div class="card"><div class="metric" id="r-useful">0%</div><div class="metric-label">注入有用率</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>检索追踪详情</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>时间</th><th>后端</th><th>查询实体</th><th>候选</th><th>注入字符</th><th>精度</th><th>有用</th><th>场景</th></tr></thead>
      <tbody id="t-retrieval"></tbody>
    </table></div>
  </div>
</section>
"""

MODEL = """\
<section id="panel-model" class="section">
  <div class="bento">
    <div class="card">
      <h2>路由模型状态</h2>
      <table style="min-width:auto"><tr><td>当前模型</td><td id="m-name" class="mono">-</td></tr>
      <tr><td>准确率</td><td id="m-accuracy">-</td></tr>
      <tr><td>训练数据</td><td id="m-data">0 条</td></tr>
      <tr><td>Fallback 数</td><td id="s-fallbacks">0</td></tr></table>
    </div>
    <div class="card">
      <h2>自动训练</h2>
      <button class="btn" onclick="triggerRetrain()">手动触发训练</button>
      <div id="retrain-progress" style="margin-top:12px"></div>
    </div>
  </div>
  <div class="bento" style="margin-top:18px">
    <div class="card full">
      <h2>Fallback 分析 <span class="metric" id="fb-total" style="font-size:20px;margin-left:12px"></span></h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
        <div><h3 class="mini" style="margin-bottom:8px">按后端</h3>
          <table style="min-width:auto"><thead><tr><th>后端</th><th>次数</th><th>占比</th><th></th></tr></thead><tbody id="fb-by-backend"></tbody></table>
        </div>
        <div><h3 class="mini" style="margin-bottom:8px">按意图</h3>
          <table style="min-width:auto"><thead><tr><th>意图</th><th>次数</th><th>占比</th></tr></thead><tbody id="fb-by-intent"></tbody></table>
        </div>
      </div>
      <h3 class="mini" style="margin:16px 0 8px">小时趋势</h3>
      <div id="fb-hourly" style="height:100px;display:flex;align-items:flex-end"></div>
    </div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>Fallback 日志</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>时间</th><th>查询</th><th>原后端</th><th>意图/原因</th></tr></thead>
      <tbody id="t-fallbacks"></tbody>
    </table></div>
  </div>
</section>
"""

HEALTH = """\
<section id="panel-health" class="section">
  <div class="bento">
    <div class="card"><div class="metric" style="color:var(--green)" id="h-healthy">0</div><div class="metric-label">健康</div></div>
    <div class="card"><div class="metric" style="color:var(--amber)" id="h-degraded">0</div><div class="metric-label">降级</div></div>
    <div class="card"><div class="metric" style="color:var(--red)" id="h-dead">0</div><div class="metric-label">宕机</div></div>
    <div class="card"><div class="metric" style="color:var(--muted)" id="h-cooled">0</div><div class="metric-label">冷却中</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>后端健康详情</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>名称</th><th>健康</th><th>分数</th><th>延迟ms</th><th>CB</th><th>CB失败</th><th>CB调用</th><th>连败</th><th>冷却</th><th>错误</th></tr></thead>
      <tbody id="t-health"></tbody>
    </table></div>
  </div>
</section>
"""

CLIENT_KEYS = """\
<section id="panel-client-keys" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="ck-total">0</div><div class="metric-label">总 Key 数</div></div>
    <div class="card"><div class="metric" style="color:var(--green)" id="ck-enabled">0</div><div class="metric-label">启用</div></div>
    <div class="card"><div class="metric" style="color:var(--red)" id="ck-disabled">0</div><div class="metric-label">禁用</div></div>
    <div class="card"><div class="metric" style="color:var(--cyan)" id="ck-active-today">0</div><div class="metric-label">今日活跃</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>客户端 Key 管理
      <button class="btn" onclick="showCreateKeyForm()">+ 发放 Key</button>
    </h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Key</th><th>标签</th><th>状态</th><th>日限</th><th>月限</th><th>日用量</th><th>月用量</th><th>最后使用</th><th>允许URL</th><th>操作</th></tr></thead>
      <tbody id="t-client-keys"></tbody>
    </table></div>
  </div>
</section>
"""

KEYS = """\
<section id="panel-keys" class="section">
  <div class="card full">
    <h2>Key-URL 清单
      <input class="search" id="key-filter" placeholder="搜索..." oninput="renderKeyUrlTable()" style="max-width:200px">
    </h2>
    <div class="table-wrap"><table>
      <thead><tr><th>名称</th><th>URL</th><th>Key</th><th>模型</th><th>协议</th><th>操作</th></tr></thead>
      <tbody id="t-key-url"></tbody>
    </table></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>Provider Key Pool</h2>
    <div id="key-pool-info"></div>
  </div>
</section>
"""

AGENTS = """\
<section id="panel-agents" class="section">
  <div class="card full">
    <h2>Agent Task Audit</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Task ID</th><th>状态</th><th>模式</th><th>仓库</th><th>目标</th><th>事件</th><th>下一步</th></tr></thead>
      <tbody id="t-agent-audit"></tbody>
    </table></div>
  </div>
</section>
"""

AGENT_TASKS = """\
<section id="panel-agent-tasks" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="at-total">0</div><div class="metric-label">总任务</div></div>
    <div class="card"><div class="metric" style="color:var(--amber)" id="at-running">0</div><div class="metric-label">运行中</div></div>
    <div class="card"><div class="metric" style="color:var(--green)" id="at-completed">0</div><div class="metric-label">已完成</div></div>
    <div class="card"><div class="metric" style="color:var(--red)" id="at-failed">0</div><div class="metric-label">失败</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>Agent 任务列表
      <div class="toolbar">
        <input class="search" id="at-filter" placeholder="搜索任务..." oninput="renderAgentTasks()" style="max-width:200px">
      </div>
    </h2>
    <div class="filter-bar">
      <button class="btn active" id="at-all" onclick="filterAgentTasks('')">全部</button>
      <button class="btn" id="at-running" onclick="filterAgentTasks('running')">运行中</button>
      <button class="btn" id="at-completed" onclick="filterAgentTasks('completed')">已完成</button>
      <button class="btn" id="at-failed" onclick="filterAgentTasks('failed')">失败</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>状态</th><th>Worker</th><th>后端</th><th>描述</th><th>创建时间</th><th>操作</th></tr></thead>
      <tbody id="t-agent-tasks"></tbody>
    </table></div>
  </div>
  <div id="at-detail-card" class="card full" style="margin-top:18px;display:none">
    <h2>任务详情 <button class="btn ghost" onclick="hideTaskDetail()">关闭</button></h2>
    <div id="at-detail-content"></div>
  </div>
</section>
"""

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

__all__ = [
    "AGENT_TASKS",
    "AGENTS",
    "ALERTS",
    "BACKENDS",
    "CLIENT_KEYS",
    "CONFIG",
    "DEVICES",
    "HEALTH",
    "KEYS",
    "LIVE_LOGS",
    "MODEL",
    "OVERVIEW",
    "RETRIEVAL",
    "TRAFFIC",
]
