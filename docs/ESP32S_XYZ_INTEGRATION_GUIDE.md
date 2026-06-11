# ESP32S_XYZ 集成指南

**创建日期**: 2026-06-11
**状态**: 已完成
**协议版本**: lima-device-v1 ↔ Edge-C

---

## 概述

本指南介绍如何将 `esp32S_XYZ` AI 写字机设备接入 LiMa 设备网关。

**已实现功能**：
- ✅ 协议转换：lima-device-v1 ↔ Edge-C
- ✅ 会话管理：session_id 生成与存储
- ✅ 任务下发：home / run_path / get_device_info
- ✅ 事件上报：accepted / running / progress / done / failed
- ✅ 测试覆盖：29 个单元/集成测试

**未实现功能**（后续工作）：
- ⏳ 实物硬件验证
- ⏳ 绘画能力迁移（draw_generated, SVG 生成）
- ⏳ 设备绑定/激活逻辑
- ⏳ VPS 部署

---

## 快速开始

### 1. 运行测试

```bash
# 协议转换测试
python -m pytest tests/test_esp32s_adapter_protocol.py -v

# 会话管理测试
python -m pytest tests/test_esp32s_adapter_session.py -v

# 桥接集成测试
python -m pytest tests/test_esp32s_adapter_bridge.py -v

# 全量测试
python -m pytest tests/test_esp32s_adapter* -v
```

### 2. 使用适配器

```python
from esp32s_adapter.bridge import ESP32SBridge

# 创建桥接器
bridge = ESP32SBridge()

# 连接设备
hello = await bridge.connect_device("dev_001")
print(hello["capabilities"])  # ['home', 'run_path', ...]

# 下发任务
lima_task = {
    "type": "task_dispatch",
    "device_id": "dev_001",
    "task_id": "task_123",
    "capability": "home",
    "params": {}
}
edge_c_task = await bridge.dispatch_task(lima_task)

# 接收事件
event = await bridge.recv_event("dev_001", timeout=5.0)
print(event["phase"])  # "done"
```

---

## 协议映射

### 下行：LiMa → Edge-C

| LiMa 字段 | Edge-C 字段 | 说明 |
|-----------|-------------|------|
| `type: task_dispatch` | `type: motion_task` | 消息类型 |
| `device_id` | `device_id` | 设备 ID |
| `task_id` | `task_id` | 任务 ID |
| `capability` | `capability` | 能力类型 |
| `params` | `params` | 参数 |
| - | `source: "client"` | 固定值 |
| - | `route_policy` | 自动生成 |

### 上行：Edge-C → LiMa

| Edge-C 字段 | LiMa 字段 | 说明 |
|-------------|-----------|------|
| `type: motion_event` | `type: motion_event` | 消息类型 |
| `session_id` | - | 移除 |
| `device_id` | `device_id` | 设备 ID |
| `task_id` | `task_id` | 任务 ID |
| `phase` | `phase` | 阶段 |
| `progress` | `progress` | 进度（可选）|
| `error_code` + `error_message` | `error` | 错误信息 |

---

## route_policy 生成规则

适配器自动为每个任务生成 `route_policy`：

```python
# 控制类任务（home, pause, resume, stop）
{
    "route_role": "device_control",
    "model_required": False,
    "primary_strategy": "deterministic",
    "artifact_required": "none"
}

# 路径执行任务（run_path）
{
    "route_role": "device_write",
    "model_required": False,
    "primary_strategy": "provided_path",
    "artifact_required": "none"
}

# 未知任务
{
    "route_role": "device_unknown",
    "model_required": False,
    "primary_strategy": "planner_required",
    "artifact_required": "none"
}
```

---

## session_id 处理

**Edge-C 要求**：上行 `motion_event` 必须包含 `session_id`。

**适配器方案**：
- 设备连接时生成：`lima-esp32s-{device_id}-{timestamp}`
- 下行任务不包含 `session_id`
- 上行事件转换时移除 `session_id`

---

## 测试覆盖

| 测试类型 | 文件 | 测试数 | 状态 |
|---------|------|--------|------|
| 协议转换 | `test_esp32s_adapter_protocol.py` | 11 | ✅ |
| 会话管理 | `test_esp32s_adapter_session.py` | 10 | ✅ |
| 桥接集成 | `test_esp32s_adapter_bridge.py` | 8 | ✅ |
| **总计** | - | **29** | **✅** |

---

## 架构图

```
┌─────────────────────────────────────┐
│   LiMa device_gateway               │
│   (lima-device-v1 protocol)         │
└──────────────┬──────────────────────┘
               │
               │ task_dispatch / motion_event
               │
┌──────────────▼──────────────────────┐
│   ESP32SBridge                      │
│   - SessionManager                  │
│   - Protocol Converter              │
└──────────────┬──────────────────────┘
               │
               │ motion_task / motion_event
               │ (Edge-C protocol)
               │
┌──────────────▼──────────────────────┐
│   ESP32S_XYZ Device (U8 Firmware)   │
│   - WebSocket Connection            │
│   - Motion Controller               │
└─────────────────────────────────────┘
```

---

## 已知限制

1. **仅支持 fake 设备测试**：未接入实物硬件
2. **route_policy 简化**：所有 run_path 任务统一为 `device_write`
3. **无持久化**：会话存储在内存，重启丢失
4. **无重连逻辑**：设备断线需重新连接

---

## 后续工作

### Week 5: 实物硬件验证
- 接入真实 esp32S_XYZ 设备
- WebSocket 连接稳定性测试
- 长时间运行测试

### Week 6: 绘画能力迁移
- `draw_generated` 能力支持
- SVG 生成管线集成
- DashScope API 接入

### Week 7: 生产化部署
- VPS 部署脚本
- 监控告警配置
- 故障恢复流程

---

## 参考文档

- [协议适配器设计](ESP32S_XYZ_PROTOCOL_ADAPTER_DESIGN.md)
- [esp32S_XYZ 架构定稿](../esp32S_XYZ/docs/架构定稿-v2.md)
- [LiMa 设备网关协议](device_gateway/protocol.py)
