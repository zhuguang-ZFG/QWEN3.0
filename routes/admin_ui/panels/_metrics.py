"""Metrics-focused panels: overview, traffic log, backends list."""

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
