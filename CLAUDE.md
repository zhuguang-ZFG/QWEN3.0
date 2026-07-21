# DLC 绘图服务 — Cursor 速览

> 完整规范：[`docs/AGENTS_REFERENCE_CN.md`](docs/AGENTS_REFERENCE_CN.md)。入口：[`AGENTS.md`](AGENTS.md)。

## 架构

```text
server_dlc.py → dlc_api/ → dlc_core/ → device_gateway/ → ESP32 (WSS)
小智 MCP → dlc_mcp/
小程序 → /device/v1/app/* + 语音
```

旧 `routing_engine*` / `server.py` 聊天栈已删除。

## 原则

1. 文档先行；过期文档直接删除
2. 单文件 ≤300 行，单函数 ≤50 行
3. Ponytail 第一；pytest / ruff / 无静默吞异常
4. 主树默认集成台；写代码用 worktree（`AGENTS.md` 硬规则 8）

## 关键文档

| 文档 | 用途 |
|------|------|
| `STATUS.md` | 当前状态 |
| `docs/README.md` | 文档索引 |
| `docs/ARCHITECTURE.md` | 架构 |
| `docs-site/api/voice.md` | 语音 API |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 部署 |
