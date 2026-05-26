# LiMa Fetch MCP smoke (radar §七)

> **Status:** Active | **Default off:** `LIMA_FETCH_MCP=0`

## 目标

验证官方 Fetch MCP（网页抓取 → Markdown）可在 LiMa Code Worker 侧启用。

## 推荐方式（Python）

npm 包 `@modelcontextprotocol/server-fetch` 在部分 registry 不可用；LiMa 使用 PyPI 包：

```powershell
pip install mcp-server-fetch
$env:LIMA_FETCH_MCP=1
python scripts/smoke_fetch_mcp.py
python scripts/smoke_fetch_mcp.py --live
```

MCP 配置示例：

```json
{
  "mcpServers": {
    "fetch": {
      "command": "python",
      "args": ["-m", "mcp_server_fetch"]
    }
  }
}
```

## 可选 npx 路径

```powershell
$env:LIMA_FETCH_MCP=1
$env:LIMA_FETCH_MCP_USE_NPX=1
python scripts/smoke_fetch_mcp.py
```

## 参考

- [modelcontextprotocol/servers — fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)
- `docs/LC_W_PLAYWRIGHT_VERIFY.md`（浏览器验收互补）
