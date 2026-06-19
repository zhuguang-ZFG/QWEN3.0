"""Admin UI panel — Overview dashboard."""

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
