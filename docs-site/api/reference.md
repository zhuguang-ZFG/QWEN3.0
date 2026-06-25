---
title: OpenAPI 参考
aside: false
head:
  - - script
    - src: https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js
      integrity: sha384-0GrsyTQc9Oqd8h+b2dbc4XdR2T/DYpy0tLNNstyx+LBMUyiBbcWPbEs9aRmUcaxD
      crossorigin: anonymous
---

# OpenAPI 参考

本页从 `openapi.yaml` 自动生成，包含 LiMa 所有公开端点的请求/响应示例。

<ClientOnly>
  <div class="redoc-wrap">
    <redoc
      spec-url="/docs/openapi.yaml"
      theme='{"colors":{"primary":{"main":"#06b6d4"},"success":{"main":"#10b981"},"warning":{"main":"#f59e0b"},"error":{"main":"#f43f5e"},"text":{"primary":"#f0f4f8","secondary":"#9aa4b2"},"background":"#07070f","codeBlock":{"background":"#0c0c16"}},"typography":{"fontFamily":"Geist, system-ui, sans-serif","code":{"fontFamily":"Geist Mono, monospace"}}}'
      hide-loading
      native-scrollbars
    ></redoc>
  </div>
</ClientOnly>

<style>
.redoc-wrap {
  margin: 0 -24px;
  min-height: 600px;
  background: var(--bg);
}
.redoc-wrap redoc {
  display: block;
}
</style>
