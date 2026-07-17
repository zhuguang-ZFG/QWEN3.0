# 语音交互 API

LiMa 设备小程序语音链路：**按住说话 REST 转写** + **实时 WS 流式 ASR**（M2）。

OpenAPI 契约见 [OpenAPI 参考](/api/reference)（含 `/voice/transcribe`、`/voice/ticket`、`/voice/ws`、`/v1/voice`）。

## 按住说话（REST）

```http
POST /device/v1/app/voice/transcribe
Authorization: Bearer <JWT>
Content-Type: multipart/form-data

audio=<WAV 或 raw PCM>
device_id=<可选，绑定设备时写入聊天历史>
```

- 采样率：16 kHz，16-bit，单声道
- 最短 PCM：约 100 ms（默认 3200 字节，可通过 `LIMA_VOICE_MIN_PCM_BYTES` 调整）
- 响应含 `text`、`intent`（如 `draw_generated` / `write_text`）

## 实时语音 WebSocket

```text
wss://chat.donglicao.com/device/v1/app/voice/ws?ticket=<ticket>
wss://chat.donglicao.com/device/v1/app/voice/ws?ticket=<ticket>&device_id=<optional>
wss://chat.donglicao.com/v1/voice?ticket=<ticket>   # 小程序兼容别名
```

可选设备绑定：`device_id` / `device-id`（query）或 `device-id`（header，对齐社区小智服务端）。若提供，服务端校验当前账号对该设备有 owner/control 权限，否则关闭连接（`4403`）且**不消耗** ticket。WS 仍只返回 `transcript`，不因设备 id 持久化音频。

### 连接流程

1. 用 JWT 换取短效 ticket（**勿**在 Query 里传 JWT）：

```http
POST /device/v1/app/voice/ticket
Authorization: Bearer <JWT>
```

响应：

```json
{
  "ticket": "tk-xxxxxxxx",
  "expires_in": 30
}
```

> `expires_in` 与 `voice_app_ws_ticket.TTL_SECONDS` 一致（30 秒）；ticket **单次使用**，绑定当前账号。
> 进入会话前失败（槽满 4429、ASR 不可用 1013、ASR `session.start` 失败 1011 等）**不消耗** ticket，TTL 内可重试；仅在 ASR start 成功后才消耗。`device_id` 仍为可选。

2. 使用 ticket 连接 WS，发送 **PCM 二进制帧**，结束时发送文本 `stop`。

### 音频格式

- 采样率：16 kHz
- 位深：16-bit
- 声道：单声道（mono）
- 推荐帧大小：**1280 字节**（约 40 ms，与小程序 `RecorderManager.frameSize` 一致）
- 服务端会按帧 pacing 转发至 DashScope Paraformer（启用 `LIMA_VOICE_STREAM_ASR_MODEL` 时）

### 客户端消息

| 方向 | 类型 | 说明 |
|------|------|------|
| 客户端 → 服务端 | 二进制 | PCM 音频帧 |
| 客户端 → 服务端 | 文本 `stop` | 结束录音并请求最终转写 |
| 客户端 → 服务端 | 文本 `ping` | 保活（建议 30s 间隔） |
| 服务端 → 客户端 | JSON `transcript` | `{ "type":"transcript", "text":"...", "is_final": false\|true }` |
| 服务端 → 客户端 | JSON `pong` | 响应 `ping` |
| 服务端 → 客户端 | JSON `error` | 如音频过短、ASR 失败 |

### 处理流程（M2）

```text
小程序 PCM 帧 → WS 缓冲/流式 ASR → transcript（仅文本）
  → 小程序侧 resolve_voice_task / 或再调 REST transcribe → 意图确认 → 设备派发
```

> WS **不返回** `intent`；与 REST `/voice/transcribe` 不同，意图解析在拿到最终 `transcript` 后由客户端完成。

默认 WS 为 **缓冲模式**（stop 时一次性 qwen3-asr-flash）。真机逐帧录音可设置：

```env
LIMA_VOICE_STREAM_ASR_MODEL=paraformer-realtime-v2
```

## 环境变量（摘要）

| 变量 | 默认 | 说明 |
|------|------|------|
| `LIMA_VOICE_ENABLED` | `0` | 启用语音 |
| `LIMA_VOICE_ASR_PROVIDER` | `dashscope` | ASR 提供商 |
| `DASHSCOPE_ASR_MODEL` | `qwen3-asr-flash` | REST 按住说话 |
| `LIMA_VOICE_STREAM_ASR_MODEL` | 空 | WS 流式模型（空则缓冲模式） |
| `LIMA_VOICE_MIN_PCM_BYTES` | `3200` | 最短有效 PCM |
| `LIMA_VOICE_STREAM_PCM_FRAME_BYTES` | `1280` | 流式分帧大小 |
| `LIMA_VOICE_STREAM_FRAME_INTERVAL_MS` | `40` | 分帧 pacing 间隔 |

## 语音任务审批

部分语音触发的任务需要用户确认：

```http
POST /device/v1/app/tasks/{task_id}/approve
POST /device/v1/app/tasks/{task_id}/reject
```

详见 [设备控制 API](/api/device-control)。
