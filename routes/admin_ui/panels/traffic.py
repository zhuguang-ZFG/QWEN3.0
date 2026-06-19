"""Admin UI panel — Traffic / request logs."""

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
