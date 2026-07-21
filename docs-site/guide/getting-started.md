# 快速开始（DLC）

> 更新日期：2026-07-21
> 本仓对外能力是 **绘图/写字/设备/小程序语音**，不是多后端 Chat Completions。

## 前置

- DLC API token 或小程序账号体系（见 [认证](/api/authentication)）
- 设备联调见仓库 `docs/DEVICE_DEVELOPER_GUIDE_CN.md`

## 1. 健康检查

```bash
curl -sS https://chat.donglicao.com/health
```

## 2. 小程序语音（转写）

见 [语音 API](/api/voice)：`POST /device/v1/app/voice/transcribe` 或 ticket 后连 `/v1/voice`。

## 3. 设备任务

见 [设备控制](/api/device-control) 与仓库 `docs/openapi.yaml`。

## 4. 设备 WSS 投递

```text
POST /device/v1/ws/ticket → wss://…/device/v1/ws?ticket=…
→ hello → drain → motion_task
```

详情：`docs/DEVICE_WS_TOKEN_DEPRECATION_CN.md`。

## 对话 / LLM

由 **小智官方云** 提供；本站不再维护 `/v1/chat/completions` 接入指南。
