"""Admin UI panels — Agent audit and agent task list."""

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
