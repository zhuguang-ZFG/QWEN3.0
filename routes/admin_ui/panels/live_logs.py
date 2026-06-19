"""Admin UI panel — Live log stream."""

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
