# LiMa Firecrawl MCP smoke (radar §七)

> **Default off:** `LIMA_FIRECRAWL_MCP=0`

需 `FIRECRAWL_API_KEY` 或自托管 `FIRECRAWL_API_URL`；未配置时 smoke skip。

```powershell
$env:LIMA_FIRECRAWL_MCP=1
$env:FIRECRAWL_API_KEY="<key>"
python scripts/smoke_firecrawl_mcp.py
python scripts/smoke_firecrawl_mcp.py --live
```

MCP 配置示例：

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "<key>"
      }
    }
  }
}
```

与 LiMa 关系：雷达 §五 Firecrawl 为 LC-W 可选爬取路径；生产路由默认不依赖。
