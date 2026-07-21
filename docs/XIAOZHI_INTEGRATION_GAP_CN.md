# 小智 ↔ DLC 集成：当前缺口

> 更新日期：2026-07-21
> 旧「替换小智服务器 / routing_engine 对话」施工手册已过时并删除；以本页 + `STATUS.md` 为准。

## 现行边界

| 能力 | 归属 |
|------|------|
| 唤醒 / ASR / TTS / 普通对话 / LLM | **小智官方云** |
| 绘图 / 写字 / 路径 / 设备任务 | **本仓 DLC**（MCP + HTTP + 设备 WSS） |
| 小程序配网 / 任务 / 语音 ASR | **DLC** `/device/v1/app/*`、`/v1/voice` |

## 已知缺口（产品/工程）

| ID | 项 | 说明 |
|----|-----|------|
| P0-3 | 真机 E2E | 录音→确认→物理运动 + 设备连 DLC WSS hello |
| P0-4 | 微信提审 | 小程序发布 |
| P0-2 | U8 OPUS/PCM | 仅设备直连语音路径 |
| Profile | hello→registry | 完整 workspace 需 `register_device_profile` |
| 固件 | WSS 客户端 | 须实现 ticket + hello + drain，否则 `queued_no_delivery` |

## 不要再做的方向

- 在本仓重建多后端 chat / `routing_engine` / 完整 `voice_pipeline` 对话栈
- 用已删的 `docs/archive` 或旧 GAP 行号当施工依据

## 入口

- 架构：`docs/ARCHITECTURE.md`
- 状态：`STATUS.md`
- 设备：`docs/DEVICE_DEVELOPER_GUIDE_CN.md`
- 瘦身结论：`docs/xiaozhi-cloud/lima-slimdown-design.md`
