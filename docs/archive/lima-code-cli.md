# LiMa CLI (deepcode-cli/) — 维护模式

> **状态**: 已进入维护模式 — 不再添加新功能，仅修复关键问题
> 子模块 `deepcode-cli/` 保留，配置目录 `.lima/` 作为 OpenCode 配置参考

## 构建说明

The CLI is a Node.js (≥22) TypeScript/React/Ink terminal app. It is **not published to npm** — install from GitHub.

```bash
cd deepcode-cli
npm install
npm run build        # typecheck + lint + format check + esbuild bundle
npm run bundle       # esbuild only (fast)
npm run test         # node src/tests/run-tests.mjs
npm run lint         # eslint src/
npm run typecheck    # tsc --noEmit
```

Binary entry: `dist/cli.js` (bin name: `lima`).

## 测试

```bash
cd deepcode-cli
npm run test
```

测试套件: 507 tests, 498 pass, 2 fail (需本地服务), 7 skip

## 迁移到 OpenCode

推荐从 LiMa CLI 迁移到 OpenCode。详见 `docs/opencode-integration.md` 的「从 LiMa CLI 迁移」章节。

| LiMa CLI | OpenCode |
|---------------|----------|
| `/lima vibe` 工作流 | `Tab` 切换 Plan 模式 → 描述需求 |
| `/model` 切换模型 | `/models` 或自动路由 |
| Skills 系统 (`~/.agents/skills/`) | OpenCode agents (`.opencode/agents/`) |
| MCP 配置 (`mcpServers`) | OpenCode MCP (`mcp` 配置) |
| `/init` 初始化 | `/init` 相同命令 |
| `/undo` 撤销 | `/undo` 相同命令 |
| 通知 (`notify` 脚本) | OpenCode `attention` 设置 |
| 图片粘贴 `Ctrl+V` | 拖拽图片到终端 |
| LiMa Server 接入 | 同左，完全兼容 |
