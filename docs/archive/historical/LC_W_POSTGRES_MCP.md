# LiMa Postgres MCP smoke (radar §七)

> **Default off:** `LIMA_POSTGRES_MCP=0`

Postgres MCP 需要数据库连接串；未配置 URL 时 smoke 会 skip（非 fail）。

```powershell
$env:LIMA_POSTGRES_MCP=1
$env:LIMA_POSTGRES_MCP_URL="postgresql://user:pass@127.0.0.1:5432/lima"
python scripts/smoke_postgres_mcp.py
python scripts/smoke_postgres_mcp.py --live
```

MCP 配置示例：

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://user:pass@127.0.0.1:5432/lima"
      ]
    }
  }
}
```

> npm 包 `@modelcontextprotocol/server-postgres` 已 deprecated；Device Gateway Postgres 审计库 deferred 前仅作 smoke 基线。
