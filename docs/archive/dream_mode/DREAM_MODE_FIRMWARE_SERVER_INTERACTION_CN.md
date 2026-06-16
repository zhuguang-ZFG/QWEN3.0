# 固件与服务端交互流程深度分析

> 本文档详细分析 ESP32 固件与 LiMa 服务端的具体交互实现。
> 基于源码逐行分析，非架构隐喻。
> **最后校验**: 2026-06-16，对照 `websocket_protocol.cc`、`protocol.cc`、`protocol.py`、`device_gateway_ws_handlers.py` 逐行验证。

## 目录

1. [WebSocket 连接建立流程（双阶段握手）](#1-websocket-连接建立流程双阶段握手)
2. [消息处理流程](#2-消息处理流程)
3. [任务创建与派发流程](#3-任务创建与派发流程)
4. [运动事件处理流程](#4-运动事件处理流程)
5. [错误处理与恢复流程](#5-错误处理与恢复流程)
6. [二进制音频协议](#6-二进制音频协议)
7. [消息格式参考](#7-消息格式参考)

---

## 1. WebSocket 连接建立流程（双阶段握手）

> **重要**: 固件存在两个不同的 hello 协议，用于不同目的。
> 阶段 A 是音频通道握手（WebSocket 原生），阶段 B 是设备注册握手（LiMa 协议）。

### 阶段 A: WebSocket 音频通道握手

#### 固件端 (`websocket_protocol.cc:83-201`)

```
WebsocketProtocol::OpenAudioChannel()
   ├─ 读取配置 (Settings "websocket"):
   │   ├─ url: WebSocket 服务器地址
   │   ├─ token: 认证令牌
   │   └─ version: 协议版本 (2 或 3)
   │
   ├─ 创建 WebSocket 连接:
   │   websocket_ = network->CreateWebSocket(1)
   │
   ├─ 设置 HTTP 头:
   │   ├─ Authorization: Bearer <token>  (如果 token 无空格则自动加 Bearer 前缀)
   │   ├─ Protocol-Version: <version>     (如 "2" 或 "3")
   │   ├─ Device-Id: <MAC地址>            (如 "AA:BB:CC:DD:EE:FF")
   │   └─ Client-Id: <UUID>
   │
   ├─ 注册数据回调:
   │   websocket_->OnData(callback)
   │
   ├─ 连接服务器:
   │   websocket_->Connect(url)
   │
   ├─ 发送音频通道 hello (GetHelloMessage()):
   │   {
     "type": "hello",
     "version": 2,
     "features": {"aec": true, "mcp": true},
     "transport": "websocket",
     "audio_params": {
       "format": "opus",
       "sample_rate": 16000,
       "channels": 1,
       "frame_duration": 60
     }
   }
   │
   └─ 等待服务器 hello (10秒超时):
       xEventGroupWaitBits(WEBSOCKET_PROTOCOL_SERVER_HELLO_EVENT, 10000ms)
```

#### 服务端收到音频通道 hello

```
固件 hello 到达
   ↓
OnData callback (websocket_protocol.cc:148-163)
   ├─ cJSON_ParseWithLength(data, len)
   ├─ type == "hello"
   └─ ParseServerHello(root):
       ├─ 验证 transport == "websocket"
       ├─ 提取 session_id → session_id_
       ├─ 提取 audio_params.sample_rate → server_sample_rate_
       ├─ 提取 audio_params.frame_duration → server_frame_duration_
       └─ xEventGroupSetBits(WEBSOCKET_PROTOCOL_SERVER_HELLO_EVENT)
```

### 阶段 B: LiMa 设备注册握手

#### 固件端发送 LiMa hello

```
Application 收到网络连接事件后
   └─ 构造 LiMa hello 消息:
       {
         "type": "hello",
         "protocol": "lima-device-v1",
         "device_id": "dev_001",
         "fw_rev": "esp32s-v1.0",
         "capabilities": ["run_path", "home", "pause", "resume", "stop"],
         "model": "esp32s-xyz",
         "hw_rev": "v1.0"
       }
```

#### 服务端处理 LiMa hello (`device_gateway_ws_handlers.py:39-72`)

```
handle_hello(websocket, message, request_id)
   │
   ├─ 1. 验证设备令牌:
   │   validate_device_token(device_id, extract_ws_token(websocket))
   │   ├─ 从 Authorization 头或 ?token= 提取令牌
   │   └─ 验证令牌有效性
   │   └─ 失败 → 发送 E_UNAUTHORIZED_DEVICE 错误 → 关闭连接 (code=1008)
   │
   ├─ 2. 创建会话:
   │   session = DeviceSession(
   │       device_id=device_id,
   │       websocket=websocket,
   │       fw_rev=message["fw_rev"],
   │       capabilities=message["capabilities"]
   │   )
   │
   ├─ 3. 注册会话:
   │   previous = registry.register(session)
   │   ├─ 如果有旧会话且 websocket 不同:
   │   │   ├─ 迁移未完成任务: _reattach_tasks(session, previous.take_outstanding_tasks())
   │   │   └─ 关闭旧连接: previous.websocket.close(code=1012)
   │   └─ 迁移活跃任务: _reattach_tasks(session, active_tasks_for_device(device_id))
   │
   ├─ 4. 更新设备影子:
   │   shadow_store.update_hello(message)
   │
   ├─ 5. 发送 hello_ack:
   │   {
     "type": "hello_ack",
     "protocol": "lima-device-v1",
     "device_id": "dev_001",
     "server_time": "2026-06-16T12:00:00Z",
     ...shadow_delta  // 可选：设备影子状态差异
   }
   │
   └─ 6. 排空待派发任务:
       drain_pending_tasks(session)
       └─ 循环发送队列中的 motion_task 到设备
```

### 关键代码路径

**固件音频通道**: `websocket_protocol.cc:83-201` (OpenAudioChannel + ParseServerHello)
**固件 LiMa hello**: `application.cc` (Application 事件处理)
**服务端 hello 处理**: `device_gateway_ws_handlers.py:39-72`
**服务端 hello_ack**: `protocol.py:224-233`

### 连接超时

```
固件端:
   kTimeoutSeconds = 120  (protocol.cc:158)
   如果 120 秒无数据，IsTimeout() 返回 true
   导致 IsAudioChannelOpened() 返回 false

服务端:
   WebSocket 断开时:
   ├─ requeue_session_outstanding(session)  // 重新入队未完成任务
   └─ registry.unregister(device_id, websocket)  // 注销会话
```

---

## 2. 消息处理流程

### 固件端消息接收 (`websocket_protocol.cc:112-166`)

```
WebsocketProtocol::OnData(data, len, binary)
   │
   ├─ binary == true (音频数据)
   │   ├─ version_ == 2:
   │   │   └─ 解析 BinaryProtocol2:
   │   │       ├─ version = ntohs(bp2->version)
   │   │       ├─ type = ntohs(bp2->type)
   │   │       ├─ timestamp = ntohl(bp2->timestamp)
   │   │       ├─ payload_size = ntohl(bp2->payload_size)
   │   │       └─ payload = bp2->payload
   │   │
   │   ├─ version_ == 3:
   │   │   └─ 解析 BinaryProtocol3:
   │   │       ├─ type = bp3->type
   │   │       ├─ payload_size = ntohs(bp3->payload_size)
   │   │       └─ payload = bp3->payload
   │   │
   │   └─ on_incoming_audio_(packet)
   │
   └─ binary == false (JSON 控制消息)
       ├─ cJSON_ParseWithLength(data, len)
       ├─ type == "hello"
       │   └─ ParseServerHello(root)  // 音频通道 hello
       └─ 其他类型
           └─ on_incoming_json_(root)
               └─ Application::Run() 处理
```

### 服务端消息分发 (`device_gateway_ws.py:25-44`)

```
handle_device_ws() 消息循环
   │
   ├─ validate_uplink(raw)
   │   ├─ ensure_object(message)  // 验证是 dict
   │   ├─ require_type(message)   // 验证 type 字段存在且在 SUPPORTED_UPLINK_TYPES 中
   │   └─ validators[msg_type](obj)  // 调用对应的验证函数
   │
   ├─ msg_type == "hello"
   │   └─ handle_hello()  // 见 §1
   │
   ├─ msg_type == "heartbeat"
   │   └─ handle_heartbeat()
   │       ├─ registry.update_heartbeat(device_id, uptime_ms)
   │       ├─ shadow_store.update_heartbeat(device_id, uptime_ms)
   │       └─ 发送 heartbeat_ack:
   │           {"type": "heartbeat_ack", "device_id": "...", "uptime_ms": N, "server_time": "..."}
   │
   ├─ msg_type == "transcript"
   │   └─ handle_transcript()
   │       ├─ create_task_from_transcript(device_id, text, request_id)
   │       └─ dispatch_task_to_session(session, task) 或 enqueue_pending_task()
   │
   ├─ msg_type == "motion_event"
   │   └─ handle_motion_event()  // 见 §4
   │
   ├─ msg_type == "device_info"
   │   └─ handle_device_info()
   │       ├─ shadow_store.update_device_info(message)
   │       └─ 发送 device_info_ack
   │
   ├─ msg_type == "self_check"
   │   └─ handle_self_check()
   │       ├─ shadow_store.update_self_check(message)
   │       └─ 发送 self_check_ack
   │
   └─ msg_type == "voiceprint_sample"
       └─ handle_voiceprint_sample()
           ├─ shadow_store.validate_voiceprint_sample(message)
           ├─ upsert_voiceprint_sample(...)
           └─ 发送 voiceprint_sample_ack
```

### 关键代码路径

**消息循环**: `device_gateway_ws.py:47-93`
**消息分发**: `device_gateway_ws.py:25-44`
**处理器**: `device_gateway_ws_handlers.py:1-311`

---

## 3. 任务创建与派发流程

### 完整流程

```
用户语音/文本
    ↓
ESP32 固件
    ├─ 语音识别 (ESP-SR)
    ├─ 音频编码 (OPUS)
    └─ 发送 transcript:
       {
         "type": "transcript",
         "device_id": "dev_001",
         "text": "画一个圆",
         "request_id": "req-123"
       }
    ↓
LiMa Server
    ├─ handle_transcript()
    │   └─ create_task_from_transcript(device_id, text, request_id)
    │       └─ project_to_motion_task(device_id, voice_task, request_id)
    │           │
    │           ├─ 1. 意图解析
    │           │   └─ resolve_voice_task(text)
    │           │       ├─ parse_command(text)
    │           │       │   ├─ 精确匹配: "归零" → home
    │           │       │   ├─ 模式匹配: "画.*" → draw_generated
    │           │       │   └─ 降级: 未知 → write_text
    │           │       └─ 返回: {capability, params, source, confidence}
    │           │
    │           ├─ 2. 解析设备配置
    │           │   └─ resolve_profile(device_id, profile_id, fw_rev)
    │           │       ├─ 查找 Profile
    │           │       ├─ 验证固件兼容性
    │           │       └─ 返回: ResolvedProfile
    │           │
    │           ├─ 3. 生成路由策略
    │           │   └─ resolve_device_route_policy(voice_task, device_id, ...)
    │           │       ├─ 根据 capability 确定 route_role
    │           │       │   ├─ home/pause/resume/stop → device_control
    │           │       │   ├─ write_text → device_write
    │           │       │   ├─ draw_generated → device_draw
    │           │       │   └─ run_path → device_vector
    │           │       ├─ 选择后端
    │           │       │   ├─ device_control → deterministic (本地)
    │           │       │   ├─ device_write → deterministic (本地)
    │           │       │   ├─ device_draw → dashscope_wanx (云端)
    │           │       │   └─ device_vector → opencv_contour (本地)
    │           │       └─ 返回: route_policy dict
    │           │
    │           ├─ 4. 验证路由策略
    │           │   └─ validate_route_policy(route_policy, capability)
    │           │
    │           ├─ 5. 创建任务参数
    │           │   └─ _create_task_from_voice_task(...)
    │           │       ├─ capability == "write_text"
    │           │       │   └─ render_text_task(text)
    │           │       │       └─ 返回: {path: [{x,y,z},...], preview_svg}
    │           │       ├─ capability == "draw_generated"
    │           │       │   └─ render_svg_task(prompt) 或 render_text_task(prompt)
    │           │       └─ capability in CONTROL_CAPABILITIES
    │           │           └─ 返回: {source_capability: capability}
    │           │
    │           ├─ 6. 策略引擎检查
    │           │   └─ policy_engine.decide(capability, device_id, ...)
    │           │       └─ 返回: PolicyResult(decision, reason)
    │           │
    │           ├─ 7. 模拟执行
    │           │   └─ simulate_motion(TaskPlan)
    │           │       └─ 返回: SimResult(risk_score, warnings)
    │           │
    │           └─ 8. 创建任务
    │               └─ task = {
    │                   "type": "motion_task",
    │                   "task_id": "task-456",
    │                   "device_id": "dev_001",
    │                   "capability": "run_path",
    │                   "params": {feed: 900, path: [...]},
    │                   "route_policy": {...},
    │                   "simulation": {...}
    │               }
    │
    ├─ dispatch_task_to_session(session, task)
    │   ├─ await session.send_json(task)
    │   ├─ session.mark_task_dispatched(task)
    │   └─ mark_task_dispatched(task_id)
    │
    └─ ESP32 固件收到 task_dispatch
        └─ Application 处理任务
            ├─ 解析 capability
            ├─ 执行相应动作:
            │   ├─ home → 调用 Grbl 归零
            │   ├─ run_path → 逐段发送 G-code
            │   └─ 其他 → 相应处理
            └─ 上报 motion_event:
               {
                 "type": "motion_event",
                 "device_id": "dev_001",
                 "task_id": "task-456",
                 "phase": "running",
                 "progress": {"percent": 50}
               }
```

### 关键代码路径

**任务创建**: `device_gateway/task_creation.py:35-244`
**任务派发**: `routes/device_gateway_dispatch.py:51-66`
**意图解析**: `device_gateway/intent.py:64-122`

---

## 4. 运动事件处理流程

### 事件类型与处理

> **注意**: `validate_motion_event()` 支持 9 种 phase 值。

```
motion_event.phase (protocol.py:123):
   │
   ├─ "accepted"  — 任务已接受，开始执行
   │   └─ workflow.advance(task_id, TaskState.RUNNING)
   │
   ├─ "queued"    — 任务已排队
   │   └─ 记录状态
   │
   ├─ "running"   — 任务执行中
   │   └─ 更新进度
   │
   ├─ "progress"  — 执行进度更新
   │   └─ shadow_store.update_motion_event(message)
   │
   ├─ "done"      — 任务完成 (终态)
   │   ├─ workflow.advance(task_id, TaskState.TERMINAL)
   │   ├─ record to Outcome Ledger
   │   └─ 提取记忆 (device_memory)
   │
   ├─ "failed"    — 任务失败 (终态)
   │   ├─ execute_recovery(task_id, device_id, message)
   │   │   ├─ 检查错误码
   │   │   │   ├─ E_MISSING_PATH → retry (3次)
   │   │   │   ├─ E_LIMIT → retry (1次)
   │   │   │   ├─ E_NOT_HOMED → home
   │   │   │   ├─ E_UART_TIMEOUT → retry (2次)
   │   │   │   └─ E_ESTOP → stop
   │   │   └─ 执行恢复动作
   │   │       ├─ retry → 重新派发任务
   │   │       ├─ home → 发送 home_command
   │   │       └─ stop → 等待人工
   │   └─ workflow.advance(task_id, TaskState.RECOVERING)
   │
   ├─ "cancelled" — 任务取消 (终态)
   │   └─ workflow.advance(task_id, TaskState.TERMINAL)
   │
   ├─ "rejected"  — 任务被拒绝 (终态)
   │   └─ workflow.advance(task_id, TaskState.TERMINAL)
   │
   └─ "stopped"   — 任务被停止 (终态)
       └─ workflow.advance(task_id, TaskState.TERMINAL)
```

### 恢复决策详情

```python
# device_intelligence/recovery.py
_ACTIONS = {
    "E_MISSING_PATH": RecoveryAction("retry", 3, 2000, "路径缺失，重试"),
    "E_LIMIT": RecoveryAction("retry", 1, 500, "限位触发，冷却后重试"),
    "E_NOT_HOMED": RecoveryAction("home", 0, 0, "未回零，先回零"),
    "E_UART_TIMEOUT": RecoveryAction("retry", 2, 1000, "串口超时，等待重试"),
    "E_ESTOP": RecoveryAction("stop", 0, 0, "急停，等待人工"),
}

def should_retry(error_code: str, attempt: int) -> bool:
    action = recovery_action(error_code)
    if action.action != "retry":
        return False
    return 0 <= attempt < action.max_retries
```

### 关键代码路径

**事件处理**: `routes/device_gateway_ws_handlers.py:163-233`
**恢复决策**: `device_intelligence/recovery.py:33-46`
**工作流**: `device_workflow/orchestrator.py`

---

## 5. 错误处理与恢复流程

### 错误分类

```
MotionErrorCode (device_gateway/protocol_families.py):
   ├─ E_UNSUPPORTED_CAPABILITY → 不支持的能力
   ├─ E_MISSING_PATH → 路径数据缺失
   ├─ E_BAD_PARAMS → 参数错误
   ├─ E_U1_UNAVAILABLE → U1 运动控制器不可用
   ├─ E_DEVICE_UPDATING → 设备升级中
   ├─ E_EXECUTION_FAILED → 执行失败
   ├─ E_UNSUPPORTED_BOARD → 不支持的板型
   ├─ E_UNSUPPORTED_PROFILE → 不支持的配置
   └─ E_TIMEOUT → 执行超时
```

### 恢复流程

```
设备报告失败
    ↓
handle_motion_event()
    ↓
execute_recovery(task_id, device_id, event)
    ├─ 检查 phase == "failed"
    ├─ 提取 error.code
    ├─ 查找恢复策略
    │   └─ recovery_action(error_code)
    │       └─ 返回: RecoveryAction(action, max_retries, cooldown_ms)
    ├─ 检查重试次数
    │   └─ should_retry(error_code, attempt)
    └─ 执行恢复动作
        ├─ action == "retry"
        │   ├─ task_store.increment_retry_count(task_id)
        │   ├─ _retry_task(task_id, device_id)
        │   │   ├─ 获取任务快照
        │   │   ├─ task_store.reset_task_for_retry(task_id)
        │   │   └─ enqueue_pending_task(device_id, task)
        │   └─ 发送 motion_task_retry 到设备
        │
        ├─ action == "home"
        │   ├─ 发送 home_command 到设备
        │   └─ 记录到 ledger
        │
        └─ action == "stop"
            └─ 等待人工干预
```

### 关键代码路径

**恢复执行**: `device_gateway/task_events.py:120-153`
**恢复决策**: `device_intelligence/recovery.py:33-46`
**任务重试**: `device_gateway/task_events.py:163-176`

---

## 6. 二进制音频协议

### 协议版本

```
BinaryProtocol2 (12字节头) — protocol.h:17-24:
   ├─ version: uint16 (网络字节序)
   ├─ type: uint16 (0=OPUS, 1=JSON)
   ├─ reserved: uint32
   ├─ timestamp: uint32 (毫秒，用于服务端 AEC)
   ├─ payload_size: uint32
   └─ payload: uint8[]

BinaryProtocol3 (4字节头) — protocol.h:26-31:
   ├─ type: uint8
   ├─ reserved: uint8
   ├─ payload_size: uint16 (网络字节序)
   └─ payload: uint8[]
```

### 音频发送流程

```
ESP32 采集音频
    ↓
AudioService::ProcessAudio()
    ├─ OPUS 编码
    └─ 创建 AudioStreamPacket
        ├─ sample_rate: 24000
        ├─ frame_duration: 60ms
        ├─ timestamp: 当前时间
        └─ payload: OPUS 编码数据
    ↓
WebsocketProtocol::SendAudio(packet)
    ├─ version_ == 2
    │   └─ 构建 BinaryProtocol2
    │       ├─ version = htons(2)
    │       ├─ type = 0 (OPUS)
    │       ├─ timestamp = htonl(packet.timestamp)
    │       ├─ payload_size = htonl(payload.size)
    │       └─ 复制 payload
    ├─ version_ == 3
    │   └─ 构建 BinaryProtocol3
    │       ├─ type = 0
    │       ├─ payload_size = htons(payload.size)
    │       └─ 复制 payload
    └─ websocket_->Send(data, size, true)  // true = binary
    ↓
LiMa Server 接收
    ↓
解析二进制包
    ├─ 提取 payload
    ├─ OPUS 解码
    └─ 送入语音识别/处理
```

### 关键代码路径

**固件发送**: `websocket_protocol.cc:28-58`
**固件接收**: `websocket_protocol.cc:112-146`
**协议定义**: `protocol.h:17-31`

---

## 7. 消息格式参考

### 上行消息 (设备 → 服务端)

#### hello (`protocol.py:67-94`)

```json
{
  "type": "hello",
  "protocol": "lima-device-v1",     // 必须匹配 PROTOCOL_VERSION
  "device_id": "dev_001",           // 必须非空
  "fw_rev": "esp32s-v1.0",         // 固件版本
  "capabilities": ["run_path", "home"],  // 能力列表
  "model": "esp32s-xyz",           // 设备型号
  "hw_rev": "v1.0",                // 硬件版本
  "workspace_mm": {"x": 100, "y": 100, "z": 20},  // 工作空间
  "profile_id": "profile-1",       // 配置ID
  "request_id": "req-123"          // 可选请求ID
}
```

#### heartbeat (`protocol.py:97-103`)

```json
{
  "type": "heartbeat",
  "device_id": "dev_001",           // 必须非空
  "uptime_ms": 12345,              // 必须非负整数
  "request_id": "req-123"          // 可选
}
```

#### transcript (`protocol.py:106-110`)

```json
{
  "type": "transcript",
  "device_id": "dev_001",           // 必须非空
  "text": "画一个圆",               // 必须非空，最大500字符
  "request_id": "req-123"          // 可选
}
```

#### motion_event (`protocol.py:113-143`)

```json
{
  "type": "motion_event",
  "device_id": "dev_001",           // 必须非空 (也接受 session_id)
  "task_id": "task-456",           // 必须非空
  "phase": "running",              // 必须是: accepted/queued/running/progress/done/failed/cancelled/rejected/stopped
  "progress": {"percent": 50},     // 可选，必须是 dict
  "error": {                       // 可选，失败时必需
    "code": "E_MISSING_PATH",
    "reason": "路径数据缺失"
  },
  "request_id": "req-123"          // 可选
}
```

**error 格式变体** (`protocol.py:307-324`):
- 格式 A: `{"error": {"code": "...", "reason": "..."}}`
- 格式 B: `{"error_code": "...", "error_message": "..."}` (向后兼容)

#### device_info (`protocol.py:146-154`)

```json
{
  "type": "device_info",
  "device_id": "dev_001",
  "model": "esp32s-xyz",
  "hw_rev": "v1.0",
  "fw_rev": "esp32s-v1.0",
  "workspace_mm": {"x": 100, "y": 100, "z": 20},
  "request_id": "req-123"
}
```

#### self_check (`protocol.py:157-170`)

```json
{
  "type": "self_check",
  "device_id": "dev_001",
  "status": "ok",
  "checks": [{"name": "motor", "status": "ok"}],
  "request_id": "req-123"
}
```

#### voiceprint_sample (`protocol.py:173-194`)

```json
{
  "type": "voiceprint_sample",
  "device_id": "dev_001",
  "voiceprint_id": "vp-001",
  "sample_index": 0,
  "audio_data": "base64_encoded_audio",
  "format": "raw_pcm",             // 必须是: raw_pcm/wav/opus/g711/pcm
  "request_id": "req-123"
}
```

### 下行消息 (服务端 → 设备)

#### hello_ack (`protocol.py:224-233`)

```json
{
  "type": "hello_ack",
  "protocol": "lima-device-v1",
  "device_id": "dev_001",
  "server_time": "2026-06-16T12:00:00Z",
  ...shadow_delta                  // 可选：设备影子状态差异
}
```

#### heartbeat_ack

```json
{
  "type": "heartbeat_ack",
  "device_id": "dev_001",
  "uptime_ms": 12345,
  "server_time": "2026-06-16T12:00:00Z"
}
```

#### task_dispatch (`protocol.py:254-285`)

```json
{
  "type": "task_dispatch",
  "device_id": "dev_001",
  "task_id": "task-456",
  "capability": "run_path",
  "params": {
    "path": [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 10, "z": 0}],
    "feed": 900.0,
    "source_capability": "draw_generated",
    "prompt": "画一个圆",
    "preview_svg": "<svg>...</svg>"
  },
  "request_id": "req-123"
}
```

#### motion_task_retry (恢复重试)

```json
{
  "type": "motion_task_retry",
  "device_id": "dev_001",
  "task_id": "task-456",
  "task": { ... },                  // 完整任务对象
  "attempt": 2,
  "server_time": "2026-06-16T12:00:00Z"
}
```

#### home_command (恢复归零)

```json
{
  "type": "home_command",
  "device_id": "dev_001",
  "task_id": "task-456",
  "reason": "recovery_action_home",
  "server_time": "2026-06-16T12:00:00Z"
}
```

#### motion_event_ack

```json
{
  "type": "motion_event_ack",
  "device_id": "dev_001",
  "server_time": "2026-06-16T12:00:00Z",
  ...summary                        // 事件摘要
}
```

#### error (`protocol.py:212-221`)

```json
{
  "type": "error",
  "code": "E_PROTOCOL_VERSION",
  "message": "protocol must be lima-device-v1",
  "request_id": "req-123"          // 可选
}
```

---

## 8. 总结：关键交互时序

```
时间轴:
0ms    ESP32 建立 WebSocket 连接
5ms    ESP32 发送音频通道 hello (version, features, audio_params)
10ms   Server 解析 hello，提取 session_id 和 audio_params
15ms   ESP32 收到 server hello，音频通道建立

20ms   ESP32 发送 LiMa hello (protocol, device_id, capabilities)
25ms   Server 验证令牌，创建 DeviceSession
30ms   Server 发送 hello_ack (protocol, device_id, server_time)
35ms   ESP32 收到 hello_ack，设备注册完成

--- 任务执行 ---

100ms  用户说"画一个圆"
150ms  ESP32 语音识别完成
200ms  ESP32 发送 transcript
250ms  Server 收到 transcript
300ms  Server 解析意图: draw_generated
350ms  Server 生成路径 (render_svg_task)
400ms  Server 创建任务 (motion_task)
450ms  Server 模拟执行 (simulate_motion)
500ms  Server 发送 task_dispatch 到 ESP32
550ms  ESP32 收到任务
600ms  ESP32 开始执行 (发送 motion_event: running)
650ms  Server 记录任务状态
700ms  ESP32 执行中 (发送 motion_event: progress)
750ms  Server 更新进度
800ms  ESP32 执行完成 (发送 motion_event: done)
850ms  Server 记录完成，提取记忆
900ms  Server 发送 motion_event_ack

--- 错误恢复 ---

1000ms ESP32 报告失败 (E_MISSING_PATH)
1050ms Server 检查恢复策略: retry (max 3)
1100ms Server 发送 motion_task_retry
1150ms ESP32 重试任务
1200ms ESP32 执行成功

--- 超时处理 ---

120s   如果 120 秒无数据，固件判定超时
       IsTimeout() → true
       IsAudioChannelOpened() → false
       触发重连流程
```

---

## 9. 未解谜题

1. **音频延迟优化**：BinaryProtocol2/3 的选择策略是什么？
2. **并发任务处理**：多任务同时派发如何保证顺序？
3. **大文件传输**：长路径（>200点）如何分片传输？
4. **离线队列**：设备断连期间的任务如何持久化？
5. **OTA 协调**：固件升级期间如何处理进行中的任务？
6. **双阶段握手的必要性**：为什么音频通道和设备注册分开？能否合并？

---

*分析完毕。固件与服务端的交互流程已被完整解析，与源码逐行校验。*
