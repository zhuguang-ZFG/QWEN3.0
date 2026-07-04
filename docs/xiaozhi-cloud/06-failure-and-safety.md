# 失败处理与安全防呆分册（06-failure-and-safety）

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`。**
> 关联：`00-roadmap.md`（P3）、`03-firmware-refactor.md`、`lima-slimdown-design.md` §1.6.5 / §1.6.6
> 目标阶段：主要在 **P3** 落地，其中固件 `motion_busy_` 属于 **P2** 硬件安全底线。

---

## 1. 本分册目的

把“任务失败怎么处理”和“设备运行中防呆”从总设计稿抽出来，形成可实施、可验收的独立分册。

**证据基线：** 本分册引用的错误码、状态机、恢复策略均来自当前真实代码：
- `device_intelligence/recovery.py`
- `device_gateway/protocol.py`
- `device_gateway/task_events.py`

未实现的部分明确标注 **设计新增**，不写成既有事实。

---

## 2. 任务状态机（已落实）

**证据：`device_gateway/protocol.py`**

```python
REQUIRED_MOTION_LIFECYCLE_PHASES = frozenset({"accepted", "running"})
TERMINAL_MOTION_PHASES = frozenset({"done", "failed", "cancelled", "rejected", "stopped"})
```

完整生命周期：

```text
queued → dispatching → dispatched → accepted → running → done / failed / cancelled / rejected / stopped
```

- 非终态：`queued / dispatching / dispatched / accepted / running`
- 终态：`done / failed / cancelled / rejected / stopped`
- `failed` 终态事件**必须携带 error code**（`protocol.py` 校验：failed event missing error code 会判定为不合法）。

---

## 3. 失败处理流程

### 3.1 阶段 A：下发阶段失败

`dispatching → dispatched` 超时或发送失败：

1. 检测：`device_gateway/redis_store.py` dispatch 超时或 WS/MQTT 发送失败。
2. 恢复：`device_gateway/task_events.py` 检测 `dispatched` 超时（`dispatch_timeout`，默认约 30s），标记 `failed`。
3. 通知：走阶段 B 的通知链路。

### 3.2 阶段 B：运行阶段失败

`running → failed`：

1. 检测：设备上报 `motion_event` phase=`failed`，携带 `error` / `error_code`。
2. 恢复决策：`device_gateway/task_events.py` 调 `device_intelligence/recovery.py` 的 `recovery_action()` 与 `should_retry()`。
3. 自动重试：允许重试且未达上限 → `task_store.reset_task_for_retry()` 递增 `retry_count` 重新入队。
4. 死信：重试耗尽/不可重试 → 标记 `dead_letter`，终端事件落盘保留。
5. 通知：`device_logic/notifications.py` 经微信小程序订阅消息推送。
6. 记忆学习：`device_memory/extractor.py` 提取故障记忆。

---

## 4. 错误码与恢复策略

**证据：`device_intelligence/recovery.py`（错误码名称、动作、重试上限逐字核对）**

| 错误码 | 含义 | 动作 | 重试上限 | 状态 |
|--------|------|------|---------|------|
| `E_MISSING_PATH` | 设备未收到路径数据 | retry | 3 | 现有 ✅ |
| `E_LIMIT` | 触发限位保护 | retry | 1 | 现有 ✅ |
| `E_NOT_HOMED` | 未回零 | **home**（不是 stop） | 0 | 现有 ✅ |
| `E_UART_TIMEOUT` | 串口超时 | retry | 2 | 现有 ✅ |
| `E_ESTOP` | 急停触发 | stop | 0 | 现有 ✅ |
| `E_PATH_OUT_OF_BOUNDS` | 路径越界 | stop + 拒绝 | 0 | **设计新增**（P1/P3 加入 recovery.py） |
| `E_UNKNOWN` | 未知错误 | stop + 人工检查 | 0 | **设计新增**（P1/P3 加入 recovery.py） |

> **勘误说明：** 总设计稿曾把 `E_NOT_HOMED` 动作写成 “stop + 语音提示”，实际代码动作是 `home`（尝试回零）。本分册以代码为准。

---

## 5. 运行中防呆机制（anti-foolhardiness）

### 5.1 场景

用户对正在画画的设备说“再画一颗星星”，LLM 又下发任务 B。当前多层防护与缺口：

| 层级 | 机制 | 代码位置 | 状态 |
|------|------|---------|------|
| 固件 UART 互斥 | `uart_mutex_` + `job_mutex_` | `u1_protocol_client.h:102-103` | ✅ 已实现 |
| 固件 OTA 拦截 | `kDeviceStateUpgrading` 拒绝运动，返回 `E_DEVICE_UPDATING` | `dlc_motor_control_p1_ai_board.cc:271-277` | ✅ 已实现 |
| 服务端任务队列 | Redis `LMOVE` 原子 FIFO | `device_gateway/redis_store.py` | ✅ 已实现 |
| 服务端 dispatch 串行 | 逐条 `send_json(task)` | `device_gateway_dispatch.py` | ✅ 已实现 |
| **固件运动忙锁** | `motion_busy_` | `motion_executor.*` | ❌ **缺失** |

### 5.2 关键缺口

`uart_mutex_` 只保证**单条 UART 指令原子**，不保证**整条 PATH 序列完整**。设备在线时，任务 B 的 PATH_BEGIN/SEG/END 可能与任务 A 交错 → U1 乱序或报错。

### 5.3 防呆方案（P2 固件 + P3 服务端）

#### 层 1：固件 `motion_busy_`（P2 必须，硬件安全底线）

见 `03-firmware-refactor.md` §5。核心：`std::atomic<bool> motion_busy_`，CAS 抢占 + RAII 复位，运动中拒绝新任务返回 `"device is busy"`。`pause/resume/stop` 不加此检查。

#### 层 2：服务端 pre-check + 角色 prompt（P3 推荐，仅覆盖 dispatch 路径）

```python
# dlc_core/dispatch.py — 下发前检查（HTTP dispatch / task_store 路径）
async def dispatch_task(device_id: str, task: dict, *, channel: str = "mqtt") -> dict:
    active = task_store.active_tasks_for_device(device_id)
    if active:
        return {"task_id": "", "status": "rejected", "reason": "device_busy",
                "active_task_id": active[0].get("task_id")}
    # ... 正常下发 ...
```

角色 prompt 追加（存小智控制台）：

```text
如果写字/绘图请求返回 device_busy，请告知用户“绘图机正在执行上一个任务，请稍等”，不要重复尝试下发。
```

#### 层 3：固件 tool 拒绝响应（P2+，依赖层 1 返回值，无额外工作）

固件高层 tool 因 busy 返回 `"device is busy"` → LLM 生成 TTS“绘图机正在忙，请稍等”。

### 5.4 拒绝返回（排队拒绝，非运动安全拒绝）

| 来源 | 返回 | 用户体验 |
|------|------|---------|
| 固件 motion_busy | `"device is busy: a motion task is already running"` | LLM TTS“绘图机正在忙” |
| 服务端 active_task | `{"status": "rejected", "reason": "device_busy", "active_task_id": "..."}` | LLM TTS“正在执行任务 X，请稍等” |

---

## 6. 安全边界（路径与运动）

| 边界 | 值 | 位置 | 处理 |
|------|-----|------|------|
| 单次下发点数 | `MAX_PATH_POINTS = 200` | `device_gateway/path_validator.py` / `path_data.py` | 超限压缩/分片/拒绝（见 `02-service-refactor.md`） |
| 工作区 | 约 100×100mm | `dlc_core/safety.py`（P1 收敛） | 越界拒绝 |
| feed | 1~20000（默认 1200） | `self.motor.run_path` Property 约束 | 超限拒绝 |
| 未回零 | `E_NOT_HOMED` | recovery.py | 触发 home |
| 急停 | `E_ESTOP` | recovery.py | stop + 人工 |

> **P1 收敛项：** `device_gateway/safety.py` 的 `MAX_POINTS = 128` 与 `path_validator.py` 的 `MAX_PATH_POINTS = 200` 冲突。authoritative 采用 **200**，迁移到 `dlc_core/safety.py` 时删除 128。

---

## 7. 用户感知

- 语音：小智云 LLM 依据 `dlc.get_device_status`（P1+ tool）或失败通知生成 TTS。
- 小程序：订阅消息推送 + 任务详情页显示失败原因与重试记录。
- 运维：Prometheus 指标 + `device_ledger` 审计日志。

---

## 8. 本阶段完成标准（P3）

1. `E_PATH_OUT_OF_BOUNDS` / `E_UNKNOWN` 加入 `recovery.py` 并有测试。
2. 服务端 `dispatch_task` device_busy pre-check 落地并有测试。
3. 固件 `motion_busy_`（P2）已在真机验证运动中拒绝新任务。
4. `MAX_PATH_POINTS` 冲突已收敛为 200。
5. 失败/防呆场景验收矩阵写入 `07-validation-and-acceptance.md`。

---

## 9. Ponytail 决策

- 复用现有 `recovery.py` + `notifications.py`，不重新发明通知/恢复通道。
- 层 1（固件忙锁）是必须的硬件安全底线；层 2/3 是体验优化。
- 新增错误码只加两条（越界、未知），不过度设计错误码体系。
