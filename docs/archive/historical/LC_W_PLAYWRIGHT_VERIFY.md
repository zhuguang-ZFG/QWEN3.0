# LC-W Playwright MCP Verify（雷达 §七）

> **Status:** Active | **Created:** 2026-05-26  
> **Scope:** LiMa Code Worker 浏览器验证 tier；**默认关**（`LIMA_PLAYWRIGHT_MCP=0`）。

## 目标

为 LiMa Code 任务提供 **可重复的 UI/页面 smoke**，作为 Verify 阶段可选 MCP（不改 `routing_engine` 热路径）。

## 启用

1. 安装 Node.js 18+ 与 `npx`。
2. 复制示例配置到 LiMa Code settings（deepcode-cli / Cursor MCP）：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

示例文件：`.lima-code/mcp-playwright.example.json`

3. 环境变量（Worker / smoke）：

```env
LIMA_PLAYWRIGHT_MCP=0
```

设为 `1` 时，`scripts/smoke_playwright_mcp.py` 会探测 `npx @playwright/mcp` 是否可启动。

## Smoke

```powershell
python scripts/smoke_playwright_mcp.py          # ENABLED=0 → skip ok
$env:LIMA_PLAYWRIGHT_MCP=1
python scripts/smoke_playwright_mcp.py          # 需 Node + npx
python scripts/smoke_playwright_mcp.py --live   # 短暂拉起 MCP 进程
```

## 与 Hooks 关系

`.lima-code/skill-rules.json` 中 `lima:playwright-verify` 在 patch/test 模式提示使用 Playwright MCP 做页面验收（需 Operator 显式开 env）。

## 参考

- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- `deepcode-cli/docs/mcp.md`
