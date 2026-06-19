"""Admin UI panel — Backend management."""

BACKENDS = """\
<section id="panel-backends" class="section">
  <div class="card full">
    <h2>后端列表
      <div class="toolbar">
        <input class="search" id="backend-filter" placeholder="搜索后端..." oninput="renderBackends()" style="max-width:200px">
      </div>
    </h2>
    <div class="filter-bar">
      <button class="btn active" id="pool-all" onclick="filterPool('all')">全部</button>
      <button class="btn" id="pool-code" onclick="filterPool('code')">Code</button>
      <button class="btn" id="pool-sandbox" onclick="filterPool('sandbox')">Sandbox</button>
      <button class="btn" id="pool-general" onclick="filterPool('general')">General</button>
    </div>
    <div id="batch-bar" style="display:none;margin-bottom:12px">
      <span id="batch-count" class="mini"></span>
      <button class="btn" onclick="batchTest()">批量测试</button>
      <button class="btn danger" onclick="batchDisable()">批量删除</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr>
        <th><input type="checkbox" onchange="toggleSelectAll(this)"></th>
        <th>注册</th><th>名称</th><th>URL</th><th>模型</th><th>Key</th>
        <th>协议</th><th>能力</th><th>池</th><th>准入</th>
        <th>调用</th><th>错误率</th><th>操作</th>
      </tr></thead>
      <tbody id="t-be-list"></tbody>
    </table></div>
  </div>
  <div class="card full" style="margin-top:18px">
    <h2>添加新后端</h2>
    <div class="form">
      <input id="be-name" placeholder="名称 *">
      <input id="be-url" class="span2" placeholder="API URL">
      <input id="be-model" placeholder="模型名">
      <input id="be-key" placeholder="API Key">
      <select id="be-fmt"><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select>
      <input id="be-auth" placeholder="认证方式">
      <select id="be-tier"><option value="">自动检测</option><option value="L1">L1 免费无限</option><option value="L2">L2 免费额度</option><option value="L3">L3 免费限量</option><option value="L4">L4 付费</option></select>
      <input id="be-admission" placeholder="准入策略" class="span2">
      <button class="btn" onclick="addBackend()">添加</button>
    </div>
  </div>
</section>
"""
