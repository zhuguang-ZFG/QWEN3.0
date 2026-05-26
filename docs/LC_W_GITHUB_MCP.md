# LiMa GitHub MCP smoke (radar §七)

> **Default off:** `LIMA_GITHUB_MCP=0`

```powershell
$env:LIMA_GITHUB_MCP=1
# 可选：完整 API 调用需 token（smoke 启动检测不强制）
$env:GITHUB_PERSONAL_ACCESS_TOKEN=$env:GITHUB_TOKEN
python scripts/smoke_github_mcp.py
python scripts/smoke_github_mcp.py --live
```

MCP 配置示例：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<token>"
      }
    }
  }
}
```
