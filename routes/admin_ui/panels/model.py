"""Admin UI panel — Routing model / fallback analysis."""

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
