# ESP32S_XYZ 协议适配器设计

**日期**: 2026-06-11
**状态**: 设计
**优先级**: P0 - Week 4 核心任务
**Owner**: zhuguang-ZFG

---

## 一、目标

将 `esp32S_XYZ` AI 写字机设备接入 LiMa 设备网关，实现协议桥接，使 LiMa 可以管理该设备。

**非目标**：
- ❌ 不迁移 `esp32S_XYZ` 的业务逻辑（设备绑定/绘画引擎）
- ❌ 不修改 `esp32S_XYZ` 固件协议（U8 保持 Edge-C 协议不变）
- ❌ 不要求实物硬件验证（使用 fake device 测试）

---

## 二、协议对比

### 2.1 架构对比

**LiMa 协议** (`lima-device-v1`):
```
LiMa device_gateway (MQTT/WebSocket)
    ↓ task_dispatch
Device (U8)
    ↓ motion_event
LiMa device_gateway
```

**esp32S_XYZ 协议** (Edge-C):
```
BusinessServer → DeviceServer (HTTP)
    ↓ motion_task (WSS downlink)
U8 Firmware
    ↓ motion_event (WSS uplink)
DeviceServer → BusinessServer (HTTP callback)
```

### 2.2 关键差异

| 维度 | LiMa (lima-device-v1) | esp32S_XYZ (Edge-C) |
|------|----------------------|---------------------|
| **连接方式** | MQTT / WebSocket | WebSocket (WSS) |
| **下行消息类型** | `task_dispatch` | `motion_task` |
| **上行消息类型** | `motion_event` | `motion_event` (相同) |
| **设备握手** | `hello` + `hello_ack` | 无显式握手 |
| **心跳** | `heartbeat` | 无独立心跳 |
| **能力声明** | `capabilities[]` in `hello` | `capability` per task |
| **必需字段** | `device_id`, `task_id`, `phase` | `session_id`, `device_id`, `task_id`, `phase` |
| **路由策略** | 无 | `route_policy` (设备绘画路由) |

---

## 三、适配器架构

### 3.1 模块划分

```
esp32s_adapter/
├── __init__.py
├── protocol.py          # Edge-C ↔ lima-device-v1 协议转换
├── session.py           # WebSocket 会话管理（模拟 DeviceServer）
└── bridge.py            # 设备网关桥接层
```

### 3.2 协议映射

#### **下行：LiMa → esp32S_XYZ**

LiMa `task_dispatch` → Edge-C `motion_task`:

```python
# LiMa format
{
    "type": "task_dispatch",
    "device_id": "dev_001",
    "task_id": "task_123",
    "capability": "run_path",
    "params": {"path": [...], "feed": 500.0}
}

# 转换为 Edge-C format
{
    "type": "motion_task",
    "device_id": "dev_001",
    "task_id": "task_123",
    "capability": "run_path",
    "source": "client",  # 固定值
    "params": {"path": [...], "feed": 500.0},
    "route_policy": {    # 自动生成
        "route_role": "device_control",
        "model_required": false,
        "primary_strategy": "provided_path",
        "artifact_required": "none"
    }
}
```

#### **上行：esp32S_XYZ → LiMa**

Edge-C `motion_event` → LiMa `motion_event`:

```python
# Edge-C format
{
    "session_id": "sess_abc",
    "type": "motion_event",
    "task_id": "task_123",
    "phase": "running",
    "device_id": "dev_001",
    "capability": "run_path"
}

# 转换为 LiMa format (去掉 session_id，添加 progress)
{
    "type": "motion_event",
    "device_id": "dev_001",
    "task_id": "task_123",
    "phase": "running",
    "progress": {}  # 如果 Edge-C 有 progress 则保留
}
```

---

## 四、关键设计决策

### 4.1 `session_id` 处理

**Edge-C 要求**：上行 `motion_event` 必须包含 `session_id`。

**解决方案**：
- 适配器在设备连接时生成 `session_id`（格式：`lima-esp32s-{device_id}-{timestamp}`）
- 下行 `motion_task` 不包含 `session_id`（Edge-C schema 不要求）
- 上行 `motion_event` 从 Edge-C 提取 `session_id`，转换为 LiMa 格式时丢弃

### 4.2 `route_policy` 自动生成

**Edge-C 要求**：下行 `motion_task` 必须包含 `route_policy`。

**生成规则**：
```python
def generate_route_policy(capability: str) -> dict:
    if capability in ("home", "pause", "resume", "stop", "estop"):
        return {
            "route_role": "device_control",
            "model_required": False,
            "primary_strategy": "deterministic",
            "artifact_required": "none"
        }
    elif capability == "run_path":
        return {
            "route_role": "device_write",  # 假设是写字任务
            "model_required": False,
            "primary_strategy": "provided_path",
            "artifact_required": "none"
        }
    else:
        return {
            "route_role": "device_unknown",
            "model_required": False,
            "primary_strategy": "planner_required",
            "artifact_required": "none"
        }
```

### 4.3 握手协议兼容

**LiMa 要求**：设备连接时必须发送 `hello` 消息。

**Edge-C 现状**：无显式握手，直接开始任务通信。

**解决方案**：
- 适配器在 LiMa 端模拟 `hello` 消息（设备连接时自动发送）
- 能力列表：`["home", "run_path", "get_device_info", "pause", "resume", "stop"]`
- `fw_rev` 从环境变量或配置文件读取

---

## 五、实施计划

### Phase 1: 协议转换层（1 天）

- [ ] `protocol.py`: 实现双向消息转换函数
  - `lima_to_edge_c_task()`
  - `edge_c_to_lima_event()`
  - `generate_route_policy()`
- [ ] 单元测试：覆盖所有能力类型

### Phase 2: WebSocket 会话管理（1 天）

- [ ] `session.py`: 模拟 DeviceServer WSS 会话
  - 设备连接管理
  - `session_id` 生成与存储
  - 消息收发队列
- [ ] 集成测试：fake U8 设备连接 → 任务下发 → 事件上报

### Phase 3: 设备网关桥接（1 天）

- [ ] `bridge.py`: 连接 LiMa `device_gateway` 和适配器
  - LiMa 任务队列 → Edge-C 任务下发
  - Edge-C 事件上报 → LiMa 事件记录
- [ ] 端到端测试：LiMa API → 适配器 → fake U8 → 事件回传

### Phase 4: 文档与部署（0.5 天）

- [ ] 更新 `STATUS.md`
- [ ] 创建 `docs/ESP32S_XYZ_INTEGRATION_GUIDE.md`
- [ ] 本地验证：pytest 全量回归
- [ ] VPS 部署（可选）

---

## 六、测试策略

### 6.1 单元测试

```python
def test_lima_to_edge_c_home_task():
    lima_task = {
        "type": "task_dispatch",
        "device_id": "dev_001",
        "task_id": "t1",
        "capability": "home",
        "params": {}
    }
    edge_c = lima_to_edge_c_task(lima_task)
    assert edge_c["type"] == "motion_task"
    assert edge_c["source"] == "client"
    assert "route_policy" in edge_c
    assert edge_c["route_policy"]["route_role"] == "device_control"
```

### 6.2 集成测试

```python
async def test_fake_u8_roundtrip():
    # 启动适配器
    adapter = ESP32SAdapter()

    # 连接 fake U8 设备
    fake_u8 = FakeESP32SDevice("dev_001")
    await adapter.connect_device(fake_u8)

    # 下发 home 任务
    task = await adapter.dispatch_task("dev_001", "home", {})

    # 等待 motion_event
    events = await fake_u8.wait_for_events(timeout=5.0)
    assert any(e["phase"] == "done" for e in events)
```

### 6.3 端到端测试

使用 LiMa 现有的 `device_gateway` 测试框架：
```python
def test_esp32s_device_via_lima_gateway():
    # 通过 LiMa device_gateway 发送任务
    response = client.post("/device/task", json={
        "device_id": "esp32s-dev_001",
        "capability": "home"
    })
    assert response.status_code == 200

    # 验证事件记录
    events = get_task_events(response.json()["task_id"])
    assert events[-1]["phase"] == "done"
```

---

## 七、风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Edge-C Schema 变更 | 中 | Schema 版本检查，不兼容时告警 |
| `session_id` 生命周期管理 | 低 | 使用内存存储，设备断线时清理 |
| `route_policy` 生成不准确 | 低 | 保守策略（`device_unknown`），不影响功能 |
| WebSocket 重连逻辑 | 中 | 复用 LiMa 现有重连机制 |

---

## 八、验收标准

- [x] 设计文档完成
- [ ] 协议转换单元测试 100% 通过
- [ ] fake U8 集成测试通过
- [ ] LiMa → 适配器 → fake U8 端到端测试通过
- [ ] pytest 全量回归通过（无新失败）
- [ ] 文档更新（STATUS.md + 集成指南）

---

## 九、后续工作（非 Week 4）

- 实物硬件验证（需要 esp32S_XYZ 设备）
- 绘画能力迁移（`draw_generated`, SVG 生成管线）
- 设备绑定/激活逻辑迁移
- 多设备并发测试
