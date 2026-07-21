# 小智官方云 + DLC

> 主路线：小智官方云承载语音/对话/LLM；本仓 DLC 承载写字/绘图/路径/设备 WSS 投递。

```text
用户语音 → ESP32 U8 → 小智云 (ASR/TTS/对话)
                    → MCP tools/call → dlc_mcp / dlc_api / dlc_core
                    → device_gateway (Redis + WSS) → U8 → U1 Grbl
小程序 → /device/v1/app/* + 语音 ticket
```

## 本目录保留

| 文档 | 用途 |
|------|------|
| [`lima-slimdown-design.md`](lima-slimdown-design.md) | 瘦身设计（权威） |
| [`p0-mcp-smoke-commands.md`](p0-mcp-smoke-commands.md) | P0 MCP 冒烟 |
| [`p1-mcp-smoke-commands.md`](p1-mcp-smoke-commands.md) | P1 MCP 冒烟 |
| [`references/`](references/) | 小智官方协议缓存 |

编号长篇重构稿与 P0/P1 证据全文已删除（git history）。状态见根目录 [`STATUS.md`](../../STATUS.md)。
