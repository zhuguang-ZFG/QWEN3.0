"""Admin panels: client keys, key-URL catalog, agents, agent tasks."""

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
