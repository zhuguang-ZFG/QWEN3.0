# 设备控制 API

LiMa 设备网关为 AI 绘画/写字机提供设备绑定、任务下发、状态查询、OTA 等接口。

## 基础信息

- 设备 App API 前缀：`https://chat.donglicao.com/device/v1/app`
- 原生网关前缀：`https://chat.donglicao.com/device/v1`
- WebSocket 实时通道：`wss://chat.donglicao.com/device/v1/ws`

## 设备绑定

### 注册设备并获取激活码

```http
POST /device/v1/app/devices/register
Authorization: Bearer <USER_TOKEN>
Content-Type: application/json

{
  "macAddress": "AA:BB:CC:DD:EE:FF"
}
```

响应：

```json
{
  "activationCode": "123456",
  "code": "123456",
  "expiresIn": 300
}
```

### 绑定设备

```http
POST /device/v1/app/devices/bind
Authorization: Bearer <USER_TOKEN>
Content-Type: application/json

{
  "deviceSn": "SN-XXXXXX",
  "activationCode": "123456",
  "model": "esp32s3_xyz",
  "firmwareVer": "2.0.0",
  "hardwareVer": "1.0"
}
```

## 任务下发

### App 任务接口

```http
POST /device/v1/app/devices/{device_id}/tasks
Authorization: Bearer <USER_TOKEN>
Content-Type: application/json

{
  "text": "画一只猫"
}
```

支持的能力包括：`run_path`、`write_text`、`draw_generated`、`draw_image`、`home`、`pause`、`resume`、`stop`、`estop`、`get_device_info`。

### 原生网关任务接口

```http
POST /device/v1/tasks
Authorization: Bearer <PRIVATE_API_KEY>
Content-Type: application/json

{
  "device_id": "dev-001",
  "text": "回家归零",
  "request_id": "req-001"
}
```

响应：

```json
{
  "status": "queued",
  "sent": true,
  "queue_depth": 0,
  "task": {
    "task_id": "task-001",
    "capability": "home"
  }
}
```

## 状态查询

### 查询设备状态

```http
GET /device/v1/app/devices/{device_id}/status
Authorization: Bearer <USER_TOKEN>
```

响应：

```json
{
  "deviceId": "dev-001",
  "online": true,
  "working": false,
  "activeTaskId": null,
  "firmwareVersion": "2.0.0",
  "protocolVersion": "lima-device-v1",
  "lastSeenAt": "2026-06-25T06:00:00Z"
}
```

### 查询任务详情

```http
GET /device/v1/tasks/{task_id}
Authorization: Bearer <PRIVATE_API_KEY>
```

响应：

```json
{
  "task_id": "task-001",
  "status": "done",
  "terminal_phase": "done",
  "task": {},
  "events": [],
  "terminal_result": null
}
```

## OTA 管理

OTA 接口前缀为 `/device/v1/ota`，包含发布门、金丝雀、灰度发布等能力，详见 [OTA 升级](/device/ota)。

## WebSocket 实时通道

设备侧通过 `wss://chat.donglicao.com/device/v1/ws` 保持长连接，上传 `motion_event`、`device_info`、`self_check` 等事件。
