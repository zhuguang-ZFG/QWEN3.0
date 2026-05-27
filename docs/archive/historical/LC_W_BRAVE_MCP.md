# LiMa Brave Search MCP smoke (radar §七)

> **Default off:** `LIMA_BRAVE_MCP=0`

官方包为 `@brave/brave-search-mcp-server`（旧 `@anthropic-ai/mcp-server-brave-search` / `@modelcontextprotocol/server-brave-search` 已 404/归档）。

```powershell
$env:LIMA_BRAVE_MCP=1
$env:BRAVE_API_KEY=$env:BRAVE_SEARCH_API_KEY
python scripts/smoke_brave_mcp.py
python scripts/smoke_brave_mcp.py --live
```

与 LiMa 原生 tier 的关系：`search_gateway/brave_adapter.py` + `BRAVE_SEARCH_ENABLED=0`（HTTP API）；MCP 为 IDE/LC-W 可选路径。

MCP 配置示例：

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
      "env": {
        "BRAVE_API_KEY": "<key>"
      }
    }
  }
}
```
