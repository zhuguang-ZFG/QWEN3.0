# 小智云 + DLC 瘦身：结论摘要

> 更新日期：2026-07-21
> 状态：**已落地**（P4/P5 瘦身 + 后续 WSS/workspace）。完整长文已删，见 git history。

## 目标架构（现行）

```text
用户语音 → ESP32 U8 → 小智官方云（ASR/TTS/对话/LLM）
                    → MCP tools/call → dlc_mcp / dlc_api / dlc_core
小程序 → /device/v1/app/* + 语音 ticket
ESP32  → /device/v1/ws?ticket= → motion_task（hello/drain/push）
```

## 决策

| 项 | 选择 |
|----|------|
| 对话/语音/LLM | 小智官方云 |
| 绘图/写字/路径 | 本仓 DLC（`server_dlc`） |
| 设备协议 | MCP + 设备 WSS ticket |
| 旧多后端路由 / chat 栈 | 物理删除 |

## 实现对照

| 模块 | 路径 |
|------|------|
| 入口 | `server_dlc.py` |
| API / MCP | `dlc_api/`、`dlc_mcp/` |
| 核心 | `dlc_core/` |
| 网关 | `device_gateway/`（含 path_workspace、delivery_reaper） |
| 小程序语音 | `device_voice/`、`routes/device_app_voice*.py` |

## 仍开放

见根目录 `STATUS.md`：真机 E2E（P0-3）、微信提审（P0-4）、hello→profile registry 等。

冒烟：`p0-mcp-smoke-commands.md` / `p1-mcp-smoke-commands.md`。
