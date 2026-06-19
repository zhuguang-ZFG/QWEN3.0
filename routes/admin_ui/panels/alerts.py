"""Admin UI panel — Alert rules."""

ALERTS = """\
<section id="panel-alerts" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="alert-total">0</div><div class="metric-label">总规则数</div></div>
    <div class="card"><div class="metric" style="color:var(--green)" id="alert-active">0</div><div class="metric-label">启用中</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>告警规则
      <button class="btn" onclick="showAddAlert()">+ 添加规则</button>
    </h2>
    <div id="alert-add-form" style="display:none;margin-bottom:16px;padding:16px;border:1px solid var(--line);border-radius:16px">
      <div class="form">
        <input id="al-name" placeholder="规则名称">
        <select id="al-metric"><option value="error_rate">错误率</option><option value="latency_ms">延迟</option><option value="fallback_rate">Fallback率</option><option value="request_count">请求量</option></select>
        <select id="al-condition"><option value="gt">大于</option><option value="lt">小于</option><option value="eq">等于</option></select>
        <input id="al-threshold" type="number" placeholder="阈值" step="0.01">
        <input id="al-window" type="number" placeholder="窗口(秒)" value="300">
        <button class="btn" onclick="addAlertRule()">创建</button>
      </div>
      <button class="btn ghost" onclick="hideAddAlert()" style="margin-top:8px">取消</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>名称</th><th>指标</th><th>条件</th><th>阈值</th><th>窗口</th><th>状态</th><th>操作</th></tr></thead>
      <tbody id="t-alerts"></tbody>
    </table></div>
  </div>
</section>
"""
