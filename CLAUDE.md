# DLC 绘图服务 — Cursor 速览

> **完整规范见 [`docs/AGENTS_REFERENCE_CN.md`](docs/AGENTS_REFERENCE_CN.md)**。根目录 `AGENTS.md` 为 Cursor 短摘要。

## 当前架构（P4/P5 瘦身后）

```
server_dlc.py → dlc_api/ → dlc_core/ → device_gateway/ → ESP32
小智 MCP → dlc_mcp/ → dlc_api/
小程序 → server_dlc.py /device/v1/app/*
```

旧 `routing_engine*` / `server.py` 聊天栈 **已删除**，勿按归档文档实现。

## 原则摘要

1. 文档先行（非平凡改动 → `docs/`）
2. 单文件 ≤300 行，单函数 ≤50 行
3. Ponytail 第一：最小变更；硬门禁（pytest、ruff、无静默吞异常）不可省
4. 代码图：**CodeGraph / lima-codegraph**；禁止 GitNexus
5. 主树 `D:\QWEN3.0` 默认只读集成；写代码用独立 worktree（见 `AGENTS.md` 硬规则 8）

## 关键文档

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 完整 Agent 操作指南 |
| `STATUS.md` / `docs/PROJECT_STATUS_CN.md` | 当前状态（同步） |
| `docs-site/api/voice.md` | 小程序语音 API |
| `docs/CURSOR_TOKEN_OPTIMIZATION_PLAN_CN.md` | Cursor token / MCP 分档 |
| `docs/ARCHITECTURE.md` | 架构边界 |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 部署硬规则 |

## Cursor 专项

```powershell
powershell -File scripts/cursor_mcp_tiers.ps1 -Tier lean    # 全局 MCP
powershell -File scripts/cursor_rules_audit.ps1               # 规则/token 自检
```

项目级 `.cursor/mcp.json` 叠加 `lima-codegraph`；固件任务在 example 中加 `platformio`。
