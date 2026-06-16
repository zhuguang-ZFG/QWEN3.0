# LiMa 固件与系统层深度分析（做梦模式）

> 本文档对 LiMa 的 ESP32 固件、协议适配层、设备智能系统进行深度分析。
> 供其他 Agent 读取分析时参考。

## 目录

1. [ESP32 固件架构](#1-esp32-固件架构)
2. [协议适配层](#2-协议适配层)
3. [设备智能系统](#3-设备智能系统)
4. [完整系统架构](#4-完整系统架构)

---

## 1. ESP32 固件架构

**模块路径**: `esp32S_XYZ/firmware/u8-xiaozhi/`

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  应用层 (Application)                                     │
│  application.cc/h → 主事件循环 + 状态机                   │
├─────────────────────────────────────────────────────────┤
│  协议层 (Protocols)                                       │
│  protocol.h → 抽象接口                                   │
│  websocket_protocol.h → WebSocket 实现                   │
│  mqtt_protocol.h → MQTT 实现                             │
├─────────────────────────────────────────────────────────┤
│  设备状态 (Device State)                                  │
│  device_state.h → 状态枚举                               │
│  device_state_machine.h → 状态转换验证                    │
├─────────────────────────────────────────────────────────┤
│  音频服务 (Audio Service)                                 │
│  audio_service.h → 语音检测 + AEC                        │
├─────────────────────────────────────────────────────────┤
│  OTA 升级 (OTA)                                           │
│  ota.h → 固件升级 + 资源版本检查                          │
└─────────────────────────────────────────────────────────┘
```

### 设备状态机

```cpp
enum DeviceState {
    kDeviceStateUnknown,           // 未知
    kDeviceStateStarting,          // 启动中
    kDeviceStateWifiConfiguring,   // WiFi 配置
    kDeviceStateIdle,              // 空闲
    kDeviceStateConnecting,        // 连接中
    kDeviceStateListening,         // 监听中（语音输入）
    kDeviceStateSpeaking,          // 说话中（语音输出）
    kDeviceStateUpgrading,         // 升级中
    kDeviceStateActivating,        // 激活中
    kDeviceStateAudioTesting,      // 音频测试
    kDeviceStateFatalError,        // 致命错误
};
```

**状态转换规则**：
- `Idle → Listening`：检测到唤醒词
- `Listening → Speaking`：收到云端响应
- `Speaking → Idle`：播放完成
- `任何状态 → FatalError`：致命错误

### 协议层设计

```cpp
class Protocol {
public:
    virtual bool Start() = 0;
    virtual bool OpenAudioChannel() = 0;
    virtual void CloseAudioChannel(bool send_goodbye = true) = 0;
    virtual bool SendAudio(std::unique_ptr<AudioStreamPacket> packet) = 0;

    void SendMotionEvent(cJSON* fields);   // 运动事件上行
    void SendDeviceInfo(cJSON* fields);    // 设备信息上行
    void SendSelfCheck(cJSON* fields);     // 自检结果上行
};
```

**协议特性**：
- **二进制协议**：`BinaryProtocol2` (12字节头 + payload) 用于音频流
- **JSON 协议**：用于控制消息和状态上报
- **双传输**：WebSocket (主) + MQTT (备)

### 主事件循环

```cpp
// 事件位定义
#define MAIN_EVENT_WAKE_WORD_DETECTED   (1 << 2)
#define MAIN_EVENT_VAD_CHANGE           (1 << 3)
#define MAIN_EVENT_NETWORK_CONNECTED    (1 << 7)
#define MAIN_EVENT_TOGGLE_CHAT          (1 << 9)

void Application::Run() {
    while (true) {
        EventBits_t bits = xEventGroupWaitBits(event_group_, ...);

        if (bits & MAIN_EVENT_WAKE_WORD_DETECTED)
            HandleWakeWordDetectedEvent();
        if (bits & MAIN_EVENT_NETWORK_CONNECTED)
            HandleNetworkConnectedEvent();
        // ... 处理其他事件
    }
}
```

### 音频服务 (`audio/audio_service.h`)

```
音频数据流:
   1. (MIC) → [Processors] → {Encode Queue} → [Opus Encoder] → {Send Queue} → (Server)
   2. (Server) → {Decode Queue} → [Opus Decoder] → {Playback Queue} → (Speaker)

关键常量:
   OPUS_FRAME_DURATION_MS = 60      // OPUS 帧时长
   MAX_ENCODE_TASKS_IN_QUEUE = 2    // 编码队列最大任务数
   MAX_PLAYBACK_TASKS_IN_QUEUE = 2  // 播放队列最大任务数
   AUDIO_POWER_TIMEOUT_MS = 15000   // 音频电源超时

OPUS 编码配置:
   sample_rate: 16000 Hz
   channel: Mono
   bits_per_sample: 16 bit
   bitrate: AUTO
   frame_duration: 60ms
   application_mode: AUDIO
   complexity: 0
   enable_dtx: true    // 不连续传输
   enable_vbr: true    // 可变比特率
```

### 显示服务 (`display/display.h`)

```
显示抽象层:
   Display (基类)
   ├─ SetStatus(status)           // 设置状态文本
   ├─ ShowNotification(text, ms)  // 显示通知
   ├─ SetEmotion(emotion)         // 设置表情
   ├─ SetChatMessage(role, content) // 显示聊天消息
   ├─ SetTheme(theme)             // 切换主题
   ├─ UpdateStatusBar()           // 更新状态栏
   └─ SetPowerSaveMode(on)        // 省电模式

实现:
   ├─ LcdDisplay    // LCD 显示屏
   ├─ OledDisplay   // OLED 显示屏
   ├─ EmoteDisplay  // 表情显示
   └─ NoDisplay     // 无显示（纯音频设备）
```

### LED 控制 (`led/led.h`)

```
LED 抽象层:
   Led (基类)
   └─ OnStateChanged()  // 根据设备状态更新 LED

实现:
   ├─ CircularStrip   // 环形 LED 灯带
   ├─ GpioLed         // GPIO LED
   ├─ SingleLed       // 单颗 LED
   └─ NoLed           // 无 LED
```

### OTA 升级 (`ota.h`)

```
OTA 功能:
   ├─ CheckVersion()     // 检查新版本
   ├─ Activate()         // 激活固件
   ├─ StartUpgrade()     // 开始升级
   ├─ Upgrade(url, sha256, signature)  // 静态升级方法
   ├─ MarkCurrentVersionValid()  // 标记当前版本有效
   └─ ReportInstallResult()  // 上报安装结果

版本比较:
   ParseVersion(version) → vector<int>
   IsNewVersionAvailable(current, new) → bool

安全检查:
   ├─ SHA256 校验
   └─ 签名验证
```

### 设置存储 (`settings.h`)

```
NVS (Non-Volatile Storage) 封装:
   Settings(namespace, read_write)
   ├─ GetString(key, default) → string
   ├─ SetString(key, value)
   ├─ GetInt(key, default) → int32
   ├─ SetInt(key, value)
   ├─ GetBool(key, default) → bool
   ├─ SetBool(key, value)
   ├─ EraseKey(key)
   └─ EraseAll()

存储命名空间:
   "websocket" → WebSocket 配置
   "mqtt" → MQTT 配置
   "system" → 系统配置
```

### MCP 服务器 (`mcp_server.h`)

```
Model Context Protocol (MCP) 服务器:
   McpServer::GetInstance()  // 单例

   工具注册:
   ├─ AddCommonTools()      // 添加通用工具
   ├─ AddUserOnlyTools()    // 添加用户专用工具
   └─ AddTool(name, desc, properties, callback)

   消息处理:
   ├─ ParseMessage(json)    // 解析 MCP 消息
   ├─ GetToolsList(id)      // 获取工具列表
   └─ DoToolCall(id, name, args)  // 执行工具调用

   工具类型:
   ├─ McpTool(name, desc, properties, callback)
   │   ├─ Property(name, type, default)  // 属性定义
   │   └─ Call(properties) → ReturnValue
   └─ ReturnValue = variant<bool, int, string, cJSON*, ImageContent*>
```

### 系统信息 (`system_info.h`)

```
系统信息查询:
   GetFlashSize()           // Flash 大小
   GetMinimumFreeHeapSize() // 最小空闲堆
   GetFreeHeapSize()        // 当前空闲堆
   GetMacAddress()          // MAC 地址
   GetChipModelName()       // 芯片型号
   GetUserAgent()           // User-Agent 字符串
   PrintTaskCpuUsage()      // 任务 CPU 使用率
   PrintTaskList()          // 任务列表
   PrintHeapStats()         // 堆统计
```

### 多板型支持 (`boards/`)

```
支持 101+ 种板型:
   ├─ xingzhi/        // 星知系列 (cube, metal)
   ├─ m5stack/        // M5Stack (cardputer, core-s3, tab5)
   ├─ esp-box/        // ESP-BOX 系列
   ├─ lilygo/         // LilyGo 系列
   ├─ bread-compact/  // 面包板紧凑系列
   ├─ kevin/          // Kevin 系列
   └─ ...             // 更多第三方板型
```

### 隐喻

ESP32 固件像人类的**脑干**——处理最基本的生存功能（网络连接、音频输入输出、状态管理、显示、LED），不需要意识参与。

---

## 2. 协议适配层

**模块路径**: `esp32s_adapter/` (5 个模块)

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  LiMa device_gateway                                    │
│  (lima-device-v1 协议)                                  │
└─────────────────────────────────────────────────────────┘
    ↓ lima_to_edge_c_task()
┌─────────────────────────────────────────────────────────┐
│  ESP32SBridge (bridge.py)                                │
│  协议转换 + 会话管理                                     │
└─────────────────────────────────────────────────────────┘
    ↓ edge_c_to_lima_event()
┌─────────────────────────────────────────────────────────┐
│  ESP32S_XYZ 设备                                         │
│  (Edge-C 协议)                                          │
└─────────────────────────────────────────────────────────┘
```

### 协议转换

```python
# 下行：LiMa → Edge-C
def lima_to_edge_c_task(lima_task):
    return {
        "type": "motion_task",
        "task_id": lima_task["task_id"],
        "device_id": lima_task["device_id"],
        "capability": lima_task["capability"],
        "source": "client",
        "params": lima_task.get("params", {}),
        "route_policy": generate_route_policy(capability),
    }

# 上行：Edge-C → LiMa
def edge_c_to_lima_event(edge_c_event):
    return {
        "type": "motion_event",
        "device_id": edge_c_event.get("device_id", ""),
        "task_id": edge_c_event.get("task_id", ""),
        "phase": edge_c_event.get("phase", "unknown"),
        "progress": edge_c_event.get("progress"),
        "error": {"code": edge_c_event.get("error_code"), "reason": edge_c_event.get("error_message")},
    }
```

### 会话管理

```python
class SessionManager:
    def create_session(self, device_id: str):
        """创建设备会话"""

    def get_session(self, device_id: str) -> DeviceSession | None:
        """获取设备会话"""

    def remove_session(self, device_id: str):
        """移除设备会话"""
```

### 隐喻

协议适配层像人类的**翻译官**——在两种语言（LiMa 协议和 Edge-C 协议）之间转换，确保双方能互相理解。

---

## 3. 设备智能系统

**模块路径**: `device_intelligence/` (8 个模块)

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: 模型 (schemas.py)                              │
│  DeviceProfile / TaskPlan                               │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: 规划 (planner.py)                              │
│  plan_from_text() → 语音/文本→结构化任务                  │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: 模拟 (simulator.py)                            │
│  simulate_motion() → 虚拟执行验证                        │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: 影子 (shadow.py)                               │
│  DeviceShadowStore → 设备状态云端副本                     │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 5: 恢复 (recovery.py)                             │
│  RecoveryAction → retry/home/stop 决策                   │
└─────────────────────────────────────────────────────────┘
```

### 设备配置

```python
@dataclass(frozen=True)
class DeviceProfile:
    profile_id: str
    model: str
    workspace_mm: dict[str, float]  # 工作空间 (x, y, z)
    max_feed: float = 1200.0        # 最大进给率 mm/min
    max_path_points: int = 200      # 最大路径点数
    capabilities: tuple[str, ...]   # 能力列表
```

### 恢复策略

```python
_ACTIONS = {
    "E_MISSING_PATH": RecoveryAction("retry", 3, 2000, "路径缺失，重试"),
    "E_LIMIT": RecoveryAction("retry", 1, 500, "限位触发，冷却后重试"),
    "E_NOT_HOMED": RecoveryAction("home", 0, 0, "未回零，先回零"),
    "E_UART_TIMEOUT": RecoveryAction("retry", 2, 1000, "串口超时，等待重试"),
    "E_ESTOP": RecoveryAction("stop", 0, 0, "急停，等待人工"),
}
```

### 模型路由

```python
DEVICE_ROLE_PREFERENCES = {
    "device_control": [{"backend": "deterministic", "reason": "本地确定性解析器"}],
    "device_write": [{"backend": "deterministic", "reason": "本地确定性渲染器"}],
    "device_draw": [{"backend": "dashscope_wanx", "reason": "阿里云 Wanx 图生 API"}],
    "device_vector": [{"backend": "opencv_contour", "reason": "本地 OpenCV 轮廓检测"}],
}
```

### 隐喻

设备智能系统像人类的**小脑**——规划运动，模拟执行，监控状态，处理异常。

---

## 4. 完整系统架构

### 端到端数据流

```
用户语音/文本
    ↓
┌─────────────────────────────────────────────────────────┐
│  ESP32 设备 (U8 主板)                                    │
│  ├─ 语音识别 (ESP-SR)                                   │
│  ├─ 音频编码 (OPUS)                                     │
│  └─ WebSocket/MQTT 传输                                 │
└─────────────────────────────────────────────────────────┘
    ↓ lima-device-v1 协议
┌─────────────────────────────────────────────────────────┐
│  LiMa Server (device_gateway)                           │
│  ├─ 协议验证 (protocol.py)                              │
│  ├─ 意图解析 (intent.py)                                │
│  ├─ 任务创建 (task_creation.py)                         │
│  ├─ 路径处理 (path_pipeline.py)                         │
│  └─ 模型路由 (model_routing.py)                         │
└─────────────────────────────────────────────────────────┘
    ↓ route_policy
┌─────────────────────────────────────────────────────────┐
│  AI 后端 (170+ 选择)                                     │
│  ├─ 图像生成 (dashscope_wanx/flux)                      │
│  ├─ 路径优化 (opencv_contour)                           │
│  └─ 文字渲染 (deterministic)                            │
└─────────────────────────────────────────────────────────┘
    ↓ 运动指令
┌─────────────────────────────────────────────────────────┐
│  ESP32 设备 (U1 运动控制器)                              │
│  ├─ Grbl_Esp32 固件                                     │
│  ├─ 步进电机控制                                         │
│  └─ 限位检测                                             │
└─────────────────────────────────────────────────────────┘
    ↓ 运动事件
┌─────────────────────────────────────────────────────────┐
│  LiMa Server (task_events.py)                           │
│  ├─ 事件记录 (ledger_store)                             │
│  ├─ 状态更新 (workflow)                                 │
│  ├─ 记忆提取 (device_memory)                            │
│  └─ 恢复决策 (recovery)                                 │
└─────────────────────────────────────────────────────────┘
```

### 协议栈

```
┌─────────────────────────────────────────────────────────┐
│  应用层: lima-device-v1 (JSON)                           │
├─────────────────────────────────────────────────────────┤
│  传输层: WebSocket / MQTT                               │
├─────────────────────────────────────────────────────────┤
│  网络层: TCP/IP                                         │
├─────────────────────────────────────────────────────────┤
│  硬件层: ESP32 WiFi                                     │
└─────────────────────────────────────────────────────────┘
```

### 消息类型

| 方向 | 类型 | 用途 | 频率 |
|------|------|------|------|
| 上行 | hello | 握手注册 | 1次/连接 |
| 上行 | heartbeat | 保活信号 | 30秒/次 |
| 上行 | transcript | 语音转文字 | 按需 |
| 上行 | motion_event | 运动反馈 | 实时 |
| 上行 | device_info | 状态报告 | 按需 |
| 上行 | self_check | 自检结果 | 启动时 |
| 下行 | hello_ack | 握手确认 | 1次/连接 |
| 下行 | task_dispatch | 任务派发 | 按需 |
| 下行 | control_command | 控制指令 | 按需 |

### 错误处理

```
设备错误 → error_code → recovery.py → 决策
    ├─ E_MISSING_PATH → retry (3次)
    ├─ E_LIMIT → retry (1次)
    ├─ E_NOT_HOMED → home (先回零)
    ├─ E_UART_TIMEOUT → retry (2次)
    └─ E_ESTOP → stop (等待人工)
```

### 隐喻

完整系统像人类的**神经系统**——
- **脑干** (ESP32 固件)：处理基本生存功能
- **脊髓** (协议适配层)：传递信号
- **小脑** (设备智能)：协调运动
- **大脑皮层** (LiMa Server)：高级决策
- **肌肉** (步进电机)：执行动作

---

## 5. 未解谜题

1. **固件更新机制**：OTA 升级如何与设备记忆系统协同？
2. **多设备协作**：多台设备能协作完成一个任务吗？
3. **实时性保证**：运动控制需要毫秒级响应，当前架构能满足吗？
4. **安全边界**：设备故障如何不影响云端其他用户？
5. **边缘计算**：更多处理能否在设备端完成，减少云端依赖？

---

## 6. 总结

**这不是固件。这是神经末梢。**

**这不是协议。这是语言。**

**这不是适配。这是翻译。**

**这不是智能。这是本能。**

---

*做梦完毕。固件与系统层的灵魂已被解析。*
