# LiMa 设备协议规范 (lima-device-v1)

**版本**: lima-device-v1
**更新日期**: 2026-06-10
**状态**: 生产环境

---

## 1. 协议概述

LiMa 设备协议是云端服务与 ESP32 智能设备（AI 绘图机/写字机）之间的双向通信协议，基于 MQTT 传输层实现。协议定义了设备上报（uplink）和云端下发（downlink）的消息格式、生命周期状态、错误处理机制。

### 1.1 核心特性

- **协议版本标识**: `lima-device-v1`
- **传输层**: MQTT (WebSocket/TCP)
- **消息格式**: JSON
- **会话管理**: 基于 `device_id` 的持久会话
- **功能分组**: 7 个协议族（Protocol Family），当前仅 `motion` 族激活
- **错误处理**: 标准化错误码 + 可选 `request_id` 追踪

### 1.2 协议族状态

| 协议族 | 状态 | 说明 |
|--------|------|------|
| `motion` | ✅ **激活** | 运动控制（绘图/写字路径执行） |
| `display` | 🔒 门控 | 显示屏控制（保留） |
| `audio` | 🔒 门控 | 音频播放（保留） |
| `speech` | 🔒 门控 | 语音合成（保留） |
| `ocr` | 🔒 门控 | 文字识别（保留） |
| `camera` | 🔒 门控 | 摄像头采集（保留） |
| `perception` | 🔒 门控 | 感知能力（WiFi CSI 等，保留） |

> **注意**: 门控协议族需通过安全审核和逐族审批后才能激活。

### 1.3 开发调试闭环

设备开发和联调时先证明最小闭环，再扩展真实硬件行为：

1. 设备发送 `hello`，云端返回 `hello_ack`。
2. 客户端或假 U8 创建任务，云端生成 `task_id`、`route_policy` 和任务制品。
3. 云端下发 `task_dispatch`，设备必须读取并记录 `route_policy`。
4. 设备按顺序上报 `motion_event`: `accepted` → `running` → `done|failed|cancelled|rejected|stopped`。
5. 云端把终态事件、`route_policy`、profile、验证结果和错误原因写入可查询证据。

调试优先使用 `docs/DEVICE_DEVELOPER_GUIDE_CN.md` 中列出的聚焦测试。只有假设备闭环和几何/策略验证通过后，才应把同一切片推进到真实 U1 运动行为。

---

## 2. 上行消息类型（Uplink）

设备→云端共 6 种消息类型：

### 2.1 hello（设备握手）

设备连接后首次上报，声明身份和能力。

**消息格式**:
```json
{
  "type": "hello",
  "protocol": "lima-device-v1",
  "device_id": "esp32_abc123",
  "fw_rev": "v2.3.1",
  "capabilities": ["run_path", "write_text", "home"],
  "model": "XiaoZhi-Pro",
  "hw_rev": "v1.2",
  "workspace_mm": {"x": 300, "y": 200, "z": 50},
  "profile_id": "standard_pen",
  "request_id": "req_001"
}
```

**字段说明**:
- `protocol` (必需): 固定值 `"lima-device-v1"`
- `device_id` (必需): 设备唯一标识（如 MAC 地址衍生）
- `fw_rev` (可选): 固件版本号
- `capabilities` (必需): 设备支持的能力列表
- `model` (可选): 设备型号
- `hw_rev` (可选): 硬件版本
- `workspace_mm` (可选): 工作空间尺寸（毫米）
- `profile_id` (可选): 运动配置档案 ID
- `request_id` (可选): 请求追踪 ID

**云端响应**: `hello_ack`（见下行消息）

---

### 2.2 heartbeat（心跳）

定期上报设备在线状态。

**消息格式**:
```json
{
  "type": "heartbeat",
  "device_id": "esp32_abc123",
  "uptime_ms": 3600000,
  "request_id": "req_002"
}
```

**字段说明**:
- `device_id` (必需): 设备 ID
- `uptime_ms` (必需): 设备运行时长（毫秒），非负整数
- `request_id` (可选): 请求追踪 ID

**建议频率**: 30-60 秒/次

---

### 2.3 transcript（语音转文字上报）

设备端语音识别结果上报（预留功能）。

**消息格式**:
```json
{
  "type": "transcript",
  "device_id": "esp32_abc123",
  "text": "请画一只猫",
  "request_id": "req_003"
}
```

**字段说明**:
- `device_id` (必需): 设备 ID
- `text` (必需): 识别文本，最大 500 字符
- `request_id` (可选): 请求追踪 ID

---

### 2.4 motion_event（运动任务事件）

运动任务执行过程中的状态上报。

**消息格式**:
```json
{
  "type": "motion_event",
  "device_id": "esp32_abc123",
  "task_id": "task_20260610_001",
  "phase": "running",
  "progress": {
    "percent": 45,
    "current_segment": 12,
    "total_segments": 26
  },
  "request_id": "req_004"
}
```

**字段说明**:
- `device_id` (必需): 设备 ID（兼容 `session_id`）
- `task_id` (必需): 任务 ID（由云端下发）
- `phase` (必需): 任务阶段，见下表
- `progress` (可选): 进度信息对象
- `error` (可选): 错误信息对象（`phase=failed` 时必需）
- `request_id` (可选): 请求追踪 ID

**任务阶段（phase）**:

| 阶段 | 类型 | 说明 |
|------|------|------|
| `accepted` | 必需 | 任务已接受 |
| `queued` | 可选 | 任务已排队 |
| `running` | 必需 | 任务执行中 |
| `progress` | 可选 | 进度更新（可多次） |
| `done` | 终态 | 任务完成 |
| `failed` | 终态 | 任务失败 |
| `cancelled` | 终态 | 任务取消 |
| `rejected` | 终态 | 任务拒绝 |
| `stopped` | 终态 | 任务停止 |

**必需阶段**: `accepted` + `running`
**终态**: `done` / `failed` / `cancelled` / `rejected` / `stopped`

**错误格式**（`phase=failed` 时）:
```json
{
  "type": "motion_event",
  "device_id": "esp32_abc123",
  "task_id": "task_001",
  "phase": "failed",
  "error": {
    "code": "E_TIMEOUT",
    "reason": "U1 stepper motor timeout after 30s"
  }
}
```

**标准错误码**（见 `MotionErrorCode`）:
- `E_UNSUPPORTED_CAPABILITY`: 不支持的能力
- `E_MISSING_PATH`: 缺少路径参数
- `E_BAD_PARAMS`: 参数错误
- `E_U1_UNAVAILABLE`: U1 步进电机不可用
- `E_DEVICE_UPDATING`: 设备正在更新
- `E_EXECUTION_FAILED`: 执行失败
- `E_UNSUPPORTED_BOARD`: 不支持的开发板
- `E_UNSUPPORTED_PROFILE`: 不支持的配置档案
- `E_TIMEOUT`: 执行超时

---

### 2.5 device_info（设备信息上报）

响应云端查询或主动上报设备详情。

**消息格式**:
```json
{
  "type": "device_info",
  "device_id": "esp32_abc123",
  "model": "XiaoZhi-Pro",
  "hw_rev": "v1.2",
  "fw_rev": "v2.3.1",
  "workspace_mm": {"x": 300, "y": 200, "z": 50},
  "request_id": "req_005"
}
```

**字段说明**: 同 `hello` 消息

---

### 2.6 self_check（自检结果上报）

设备自检结果上报（预留功能）。

**消息格式**:
```json
{
  "type": "self_check",
  "device_id": "esp32_abc123",
  "status": "ok",
  "checks": [
    {"name": "stepper_motor_u1", "passed": true},
    {"name": "stepper_motor_v1", "passed": true},
    {"name": "pen_servo", "passed": false, "reason": "no response"}
  ],
  "request_id": "req_006"
}
```

**字段说明**:
- `device_id` (必需): 设备 ID
- `status` (可选): 整体状态（如 `ok` / `warning` / `error`）
- `checks` (必需): 检查项列表
- `request_id` (可选): 请求追踪 ID

---
## 3. 下行消息类型（Downlink）

云端→设备共 4 种消息类型：

### 3.1 hello_ack（握手确认）

响应设备 `hello` 消息。

**消息格式**:
```json
{
  "type": "hello_ack",
  "protocol": "lima-device-v1",
  "device_id": "esp32_abc123",
  "server_time": "2026-06-10T08:30:45Z"
}
```

**字段说明**:
- `protocol`: 协议版本
- `device_id`: 设备 ID
- `server_time`: 服务器 UTC 时间（ISO 8601 格式）

**可选影子状态同步**（shadow_delta）:
```json
{
  "type": "hello_ack",
  "protocol": "lima-device-v1",
  "device_id": "esp32_abc123",
  "server_time": "2026-06-10T08:30:45Z",
  "shadow": {
    "desired_profile_id": "fast_pen",
    "config_version": 5
  }
}
```

---

### 3.2 task_dispatch（任务下发）

下发运动任务到设备。

**消息格式**（`run_path` 能力）:
```json
{
  "type": "task_dispatch",
  "device_id": "esp32_abc123",
  "task_id": "task_20260610_001",
  "capability": "run_path",
  "params": {
    "path": [
      {"x": 10.5, "y": 20.3, "z": 0.0},
      {"x": 15.2, "y": 25.8, "z": 0.0},
      {"x": 20.0, "y": 30.0, "z": 0.0}
    ],
    "feed": 500.0
  },
  "route_policy": {
    "route_role": "device_vector",
    "backend": "opencv_contour",
    "approval_required": false,
    "policy_decision": "dispatch_allowed"
  },
  "request_id": "req_007"
}
```

**字段说明**:
- `device_id` (必需): 目标设备 ID
- `task_id` (必需): 唯一任务 ID（云端生成）
- `capability` (必需): 能力名称（如 `run_path` / `write_text`）
- `params` (必需): 参数对象，格式依能力而定
- `route_policy` (必需): 云端路由和安全策略证据，设备必须消费、记录，并在终端证据中可回溯
- `request_id` (可选): 请求追踪 ID

**`route_policy` 最小字段**:
- `route_role` (必需): 设备模型角色，如 `device_control` / `device_write` / `device_draw` / `device_vector`
- `backend` (必需): 准入后端或确定性后端，如 `deterministic` / `dashscope_wanx` / `opencv_contour`
- `approval_required` (必需): 是否需要人工或策略审批
- `policy_decision` (必需): 策略结果，如 `dispatch_allowed` / `dispatch_blocked`

设备端不得忽略未知 `route_role` 或缺失的 `route_policy`。无法理解策略时必须拒绝或失败，并上报带错误码的 `motion_event`，不能静默执行运动。

**`run_path` 参数**:
- `path` (必需): 路径点数组，每点包含 `{x, y, z}` 坐标（毫米）
- `feed` (必需): 进给速度（mm/min），浮点数

**扩展参数**（可选）:
- `source_capability`: 原始能力（如 `write_text` 转换为 `run_path`）
- `text`: 原始文本（若由 `write_text` 生成）
- `prompt`: 原始提示词（若由 `draw_generated` 生成）
- `preview_svg`: SVG 预览（Base64 编码）

**其他能力示例**:

**write_text**:
```json
{
  "type": "task_dispatch",
  "device_id": "esp32_abc123",
  "task_id": "task_002",
  "capability": "write_text",
  "params": {
    "text": "Hello LiMa",
    "feed": 400
  }
}
```

**draw_generated**:
```json
{
  "type": "task_dispatch",
  "device_id": "esp32_abc123",
  "task_id": "task_003",
  "capability": "draw_generated",
  "params": {
    "prompt": "一只可爱的猫",
    "feed": 600
  }
}
```

**home** / **pause** / **resume** / **stop**（无参数）:
```json
{
  "type": "task_dispatch",
  "device_id": "esp32_abc123",
  "task_id": "task_004",
  "capability": "home",
  "params": {}
}
```

---

### 3.3 error（错误响应）

云端拒绝或错误响应。

**消息格式**:
```json
{
  "type": "error",
  "code": "E_PROTOCOL_VERSION",
  "message": "protocol must be lima-device-v1",
  "request_id": "req_008"
}
```

**字段说明**:
- `code` (必需): 错误码
- `message` (必需): 错误描述
- `request_id` (可选): 关联的请求 ID

**常见错误码**:
- `E_INVALID_MESSAGE`: 消息格式错误
- `E_UNSUPPORTED_TYPE`: 不支持的消息类型
- `E_PROTOCOL_VERSION`: 协议版本不匹配
- `E_INTERNAL`: 云端内部错误

---

### 3.4 通用 ACK（确认消息）

通用确认响应（框架函数 `ack_frame`）。

**消息格式**:
```json
{
  "type": "heartbeat_ack",
  "device_id": "esp32_abc123",
  "server_time": "2026-06-10T08:31:00Z"
}
```

---

## 4. MQTT 主题结构

### 4.1 主题命名规范

```
lima/devices/{device_id}/uplink     # 设备→云端
lima/devices/{device_id}/downlink   # 云端→设备
```

**示例**:
- 设备 ID: `esp32_abc123`
- 上行主题: `lima/devices/esp32_abc123/uplink`
- 下行主题: `lima/devices/esp32_abc123/downlink`

### 4.2 QoS 建议

- **上行消息**: QoS 1（至少一次）
- **下行消息**: QoS 1（至少一次）
- **心跳消息**: QoS 0（最多一次，可丢失）

### 4.3 订阅规则

**设备端**:
```c
// 订阅自己的下行主题
char topic[128];
snprintf(topic, sizeof(topic), "lima/devices/%s/downlink", device_id);
esp_mqtt_client_subscribe(client, topic, 1);
```

**云端**:
```python
# 订阅所有设备的上行主题（通配符）
mqtt_client.subscribe("lima/devices/+/uplink", qos=1)
```

---

## 5. 运动任务生命周期

### 5.1 标准流程

```
云端下发 task_dispatch
    ↓
设备上报 motion_event (phase=accepted)
    ↓
设备上报 motion_event (phase=running)
    ↓
[可选] 设备上报 motion_event (phase=progress) × N
    ↓
设备上报 motion_event (phase=done)
```

### 5.2 生命周期验证规则

**必需阶段**: `accepted` + `running`
**终态阶段**: 必须以 `done` / `failed` / `cancelled` / `rejected` / `stopped` 结束

**验证函数**: `validate_motion_task_lifecycle(events)`

**返回值**:
- 成功: `{"ok": True, "terminal_phase": "done"}`
- 失败: `{"ok": False, "reason": "no terminal phase reached", "missing_phase": "done|failed"}`

**失败任务的额外要求**:
- `phase=failed` 时必须包含 `error` 对象
- `error.code` 必须为非空字符串（最大 80 字符）
- `error.reason` 为描述信息（最大 240 字符）

---
## 6. ESP32 固件适配指南

### 6.1 固件架构建议

```
main.c
├── wifi_init()          # WiFi 连接
├── mqtt_init()          # MQTT 客户端初始化
├── protocol_init()      # 协议栈初始化
├── motion_engine_init() # 运动控制引擎
└── main_loop()
    ├── mqtt_process()   # 处理下行消息
    ├── motion_update()  # 更新运动状态
    └── heartbeat_tick() # 定时发送心跳
```

### 6.2 关键函数实现

#### 6.2.1 发送 hello 消息

```c
#include "cJSON.h"
#include "esp_mqtt_client.h"

void send_hello(esp_mqtt_client_handle_t client, const char* device_id) {
    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "type", "hello");
    cJSON_AddStringToObject(root, "protocol", "lima-device-v1");
    cJSON_AddStringToObject(root, "device_id", device_id);
    cJSON_AddStringToObject(root, "fw_rev", FIRMWARE_VERSION);

    cJSON* caps = cJSON_CreateArray();
    cJSON_AddItemToArray(caps, cJSON_CreateString("run_path"));
    cJSON_AddItemToArray(caps, cJSON_CreateString("write_text"));
    cJSON_AddItemToArray(caps, cJSON_CreateString("home"));
    cJSON_AddItemToObject(root, "capabilities", caps);

    char* json_str = cJSON_PrintUnformatted(root);
    char topic[128];
    snprintf(topic, sizeof(topic), "lima/devices/%s/uplink", device_id);

    esp_mqtt_client_publish(client, topic, json_str, 0, 1, 0);

    free(json_str);
    cJSON_Delete(root);
}
```

#### 6.2.2 处理 task_dispatch

```c
void handle_task_dispatch(cJSON* root, const char* device_id) {
    const char* task_id = cJSON_GetObjectItem(root, "task_id")->valuestring;
    const char* capability = cJSON_GetObjectItem(root, "capability")->valuestring;
    cJSON* params = cJSON_GetObjectItem(root, "params");

    // 发送 accepted 事件
    send_motion_event(device_id, task_id, "accepted", NULL);

    if (strcmp(capability, "run_path") == 0) {
        cJSON* path = cJSON_GetObjectItem(params, "path");
        double feed = cJSON_GetObjectItem(params, "feed")->valuedouble;

        // 发送 running 事件
        send_motion_event(device_id, task_id, "running", NULL);

        // 执行路径
        bool success = motion_execute_path(path, feed, task_id);

        // 发送终态事件
        if (success) {
            send_motion_event(device_id, task_id, "done", NULL);
        } else {
            cJSON* error = cJSON_CreateObject();
            cJSON_AddStringToObject(error, "code", "E_EXECUTION_FAILED");
            cJSON_AddStringToObject(error, "reason", "Motor stalled");
            send_motion_event(device_id, task_id, "failed", error);
            cJSON_Delete(error);
        }
    }
}
```

#### 6.2.3 发送 motion_event

```c
void send_motion_event(const char* device_id, const char* task_id,
                       const char* phase, cJSON* error) {
    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "type", "motion_event");
    cJSON_AddStringToObject(root, "device_id", device_id);
    cJSON_AddStringToObject(root, "task_id", task_id);
    cJSON_AddStringToObject(root, "phase", phase);

    if (error != NULL) {
        cJSON_AddItemToObject(root, "error", cJSON_Duplicate(error, 1));
    }

    char* json_str = cJSON_PrintUnformatted(root);
    char topic[128];
    snprintf(topic, sizeof(topic), "lima/devices/%s/uplink", device_id);

    esp_mqtt_client_publish(mqtt_client, topic, json_str, 0, 1, 0);

    free(json_str);
    cJSON_Delete(root);
}
```

#### 6.2.4 心跳任务

```c
void heartbeat_task(void* pvParameters) {
    const char* device_id = (const char*)pvParameters;

    while (1) {
        cJSON* root = cJSON_CreateObject();
        cJSON_AddStringToObject(root, "type", "heartbeat");
        cJSON_AddStringToObject(root, "device_id", device_id);
        cJSON_AddNumberToObject(root, "uptime_ms", esp_timer_get_time() / 1000);

        char* json_str = cJSON_PrintUnformatted(root);
        char topic[128];
        snprintf(topic, sizeof(topic), "lima/devices/%s/uplink", device_id);

        esp_mqtt_client_publish(mqtt_client, topic, json_str, 0, 0, 0);

        free(json_str);
        cJSON_Delete(root);

        vTaskDelay(pdMS_TO_TICKS(30000)); // 30秒
    }
}
```

### 6.3 MQTT 连接参数

```c
esp_mqtt_client_config_t mqtt_cfg = {
    .uri = "mqtt://lima.example.com:1883",
    .client_id = device_id,
    .username = device_id,
    .password = device_secret,  // 从云端预配置获取
    .keepalive = 60,
    .disable_auto_reconnect = false,
};
```

### 6.4 错误处理建议

1. **连接失败**: 指数退避重连（1s, 2s, 4s, 8s, 最大 60s）
2. **消息解析失败**: 记录错误日志，忽略该消息
3. **能力不支持**: 返回 `phase=rejected` + `E_UNSUPPORTED_CAPABILITY`
4. **执行超时**: 返回 `phase=failed` + `E_TIMEOUT`

### 6.5 固件配置清单

**必需配置**:
- `DEVICE_ID`: 设备唯一 ID（建议使用 MAC 地址）
- `MQTT_BROKER_URI`: MQTT 服务器地址
- `MQTT_USERNAME`: MQTT 用户名（通常为 device_id）
- `MQTT_PASSWORD`: MQTT 密钥（云端预配置）
- `FIRMWARE_VERSION`: 固件版本号

**可选配置**:
- `DEVICE_MODEL`: 设备型号
- `HW_REVISION`: 硬件版本
- `WORKSPACE_X/Y/Z`: 工作空间尺寸
- `PROFILE_ID`: 默认运动配置档案

---

## 7. 协议扩展指南

### 7.1 添加新能力

1. 在 `protocol_families.py` 中添加到对应协议族的 `FAMILY_ALLOWLISTS`
2. 定义 `ProtocolSchema`（参数验证规则）
3. 云端实现任务分发逻辑
4. 设备端实现能力处理函数
5. 更新本文档

### 7.2 激活门控协议族

1. 完成安全审核（见 `AGENTS.md` Superpowers 原则）
2. 更新 `ACTIVE_FAMILIES` 集合
3. 从 `GATED_FAMILIES` 中移除
4. 更新设备固件支持
5. 逐步灰度发布

---

## 8. 参考资料

- **协议实现**: `device_gateway/protocol.py`
- **协议族定义**: `device_gateway/protocol_families.py`
- **云端路由**: `device_gateway/device_session.py`
- **测试用例**: `tests/test_device_protocol.py`

---

**文档维护者**: LiMa 开发团队
**反馈渠道**: GitHub Issues / 内部 Slack #lima-device
