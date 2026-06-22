"""Analysis panels: retrieval traces, ML model, health."""

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
