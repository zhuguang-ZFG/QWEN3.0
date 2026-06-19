"""Admin UI panels — Client keys and key-URL/provider key pool."""

CLIENT_KEYS = """\
<section id="panel-client-keys" class="section">
  <div class="bento">
    <div class="card"><div class="metric" id="ck-total">0</div><div class="metric-label">总 Key 数</div></div>
    <div class="card"><div class="metric" style="color:var(--green)" id="ck-enabled">0</div><div class="metric-label">启用</div></div>
    <div class="card"><div class="metric" style="color:var(--red)" id="ck-disabled">0</div><div class="metric-label">禁用</div></div>
    <div class="card"><div class="metric" style="color:var(--cyan)" id="ck-active-today">0</div><div class="metric-label">今日活跃</div></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>客户端 Key 管理
      <button class="btn" onclick="showCreateKeyForm()">+ 发放 Key</button>
    </h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Key</th><th>标签</th><th>状态</th><th>日限</th><th>月限</th><th>日用量</th><th>月用量</th><th>最后使用</th><th>允许URL</th><th>操作</th></tr></thead>
      <tbody id="t-client-keys"></tbody>
    </table></div>
  </div>
</section>
"""

KEYS = """\
<section id="panel-keys" class="section">
  <div class="card full">
    <h2>Key-URL 清单
      <input class="search" id="key-filter" placeholder="搜索..." oninput="renderKeyUrlTable()" style="max-width:200px">
    </h2>
    <div class="table-wrap"><table>
      <thead><tr><th>名称</th><th>URL</th><th>Key</th><th>模型</th><th>协议</th><th>操作</th></tr></thead>
      <tbody id="t-key-url"></tbody>
    </table></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>Provider Key Pool</h2>
    <div id="key-pool-info"></div>
  </div>
</section>
"""
