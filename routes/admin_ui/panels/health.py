"""Admin UI panel — Backend health."""

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
