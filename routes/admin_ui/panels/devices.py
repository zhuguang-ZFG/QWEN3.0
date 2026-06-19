"""Admin UI panel — Device gateway."""

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
