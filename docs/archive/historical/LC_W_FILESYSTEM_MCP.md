# LiMa Filesystem MCP smoke (radar §七)

> **Default off:** `LIMA_FILESYSTEM_MCP=0`

```powershell
$env:LIMA_FILESYSTEM_MCP=1
$env:LIMA_FILESYSTEM_MCP_ROOT=D:\GIT
python scripts/smoke_filesystem_mcp.py
python scripts/smoke_filesystem_mcp.py --live
```

MCP 配置示例：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:/GIT"]
    }
  }
}
```
