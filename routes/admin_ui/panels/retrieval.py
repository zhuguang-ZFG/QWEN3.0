"""Admin UI panel — Retrieval tracing."""

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
