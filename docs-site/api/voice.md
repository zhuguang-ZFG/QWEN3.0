# 语音交互 API

LiMa 提供自托管实时语音流水线，浏览器通过 WebSocket 直接与服务端交互。

## 实时语音 WebSocket

```text
wss://chat.donglicao.com/v1/voice
```

### 连接方式

可通过 Query 参数或 Header 传递 Token：

```text
wss://chat.donglicao.com/v1/voice?authorization=Bearer%20<LIMA_API_KEY>
```

::: warning
Query 参数会暴露 Token，生产环境请优先使用 ticket 或安全 header 方案。
:::

### 音频格式

- 采样率：16 kHz
- 位深：16-bit
- 声道：单声道（mono）
- 帧大小：1024 字节（512 采样点）

### 处理流程

```text
浏览器 PCM 音频 → VAD → ASR → LLM → TTS → 浏览器播放
```

## Gemini Live 代理

浏览器也可以连接 LiMa 的 `/v1/live` 端点，LiMa 将流量转发到 Gemini Live。

```text
wss://chat.donglicao.com/v1/live
```

## 获取 WebSocket Ticket

设备或客户端可先换取短效 ticket：

```http
POST /v1/ws/ticket
Authorization: Bearer <LIMA_API_KEY>
Content-Type: application/json

{
  "device_id": "dev-001",
  "token": "<DEVICE_TOKEN>"
}
```

响应：

```json
{
  "ticket": "tk-xxxxxxxx",
  "expires_in": 300
}
```

## 语音任务审批

部分语音触发的任务需要用户确认，App 可通过以下接口审批：

```http
POST /device/v1/app/tasks/{task_id}/approve
POST /device/v1/app/tasks/{task_id}/reject
```

详见 [设备控制 API](/api/device-control)。
