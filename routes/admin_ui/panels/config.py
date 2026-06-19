"""Admin UI panel — Config export / import."""

CONFIG = """\
<section id="panel-config" class="section">
  <div class="card">
    <h2>配置导出</h2>
    <p class="mini">版本: <span id="cfg-version" class="mono">-</span></p>
    <pre id="cfg-preview" style="background:rgba(8,12,20,0.6);border:1px solid var(--line);border-radius:12px;padding:12px;font-size:12px;max-height:300px;overflow:auto;margin:12px 0"></pre>
    <button class="btn" onclick="exportConfig()">导出配置</button>
  </div>
  <div class="card">
    <h2>配置导入</h2>
    <input type="file" id="config-file" accept=".json" style="margin:12px 0">
    <br><button class="btn" onclick="importConfig()">导入配置</button>
  </div>
</section>
"""
