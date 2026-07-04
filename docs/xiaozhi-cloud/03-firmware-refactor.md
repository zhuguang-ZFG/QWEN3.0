# 固件端改造分册（U8 / U1）

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`，以小智官方云承载语音/对话/LLM，以 DLC 核心承载写字/绘图/路径/设备控制。**
> 关联总设计：`docs/xiaozhi-cloud/lima-slimdown-design.md`（§1.6.6 防呆、§2、§3）
> 关联入口：`docs/xiaozhi-cloud/README.md`、`docs/xiaozhi-cloud/00-roadmap.md`
> 关联架构：`docs/xiaozhi-cloud/01-architecture.md`
> 关联未决项：`docs/xiaozhi-cloud/08-open-questions.md`（Q-01 链式调用、Q-08 motion_busy_、Q-09 一键配网）

---

## 0. 本文件目的

本分册冻结**固件端（U8 小智固件 + U1 Grbl 运动板）**在本次重构中的改造边界，明确：

- U8 已有哪些 MCP tool、协议、状态机（已验证事实）
- U8 需要新增什么（`self.plotter.*`、`motion_busy_` 防呆）
- U8↔U1 的 Edge-D UART 协议命令（已验证事实）
- 哪些属于 P2 阶段实现、哪些先冻结设计

> **Ponytail 硬规则：** 任何 ESP32 / 固件改动前，必须先加载对应 skills（`esp32`、`esp-idf-handling`、`esp-pio-handling`、`serial`、`jlink`、`openocd` 等）。本分册只冻结设计，不含真机烧录步骤。

---

## 1. 固件端已验证事实（真实源码）

### 1.1 关键文件位置

| 组件 | 路径（相对 `esp32S_XYZ/`） |
|------|---------------------------|
| U8 板级实现 | `firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc` |
| U8 运动执行器 | `.../dlc-motor-control-p1-ai/motion_executor.{h,cc}` |
| U8→U1 协议客户端 | `.../dlc-motor-control-p1-ai/u1_protocol_client.{h,cc}` |
| U8 MCP Server 基类 | `firmware/u8-xiaozhi/main/mcp_server.{h,cc}` |
| U1 协议解析 | `firmware/u1-grbl/Grbl_Esp32/src/Protocol.cpp` |
| U1 机型配置 | `firmware/u1-grbl/Grbl_Esp32/src/Machines/dlc_motor_control_p1.h` |

### 1.2 U8 已注册的 MCP tool（`dlc_motor_control_p1_ai_board.cc`）

已确认注册的运动类工具（全部 `self.motor.*`）：

| Tool | 行号 | 职责 |
|------|------|------|
| `self.motor.home` | 136 | 归位/回零 |
| `self.motor.get_status` | 143 | 查询运动状态 |
| `self.motor.get_device_info` | 150 | 查询设备信息 |
| `self.motor.pause` | 157 | 暂停 |
| `self.motor.resume` | 164 | 恢复 |
| `self.motor.stop` | 171 | 停止 |
| `self.motor.move_abs` | 178 | 绝对移动 |
| `self.motor.move_rel` | 194 | 相对移动 |
| `self.motor.run_path` | 210 | 执行路径（`path_json` + `feed`，feed 默认 1200，范围 1-20000） |

框架层通用工具（`mcp_server.cc`）：`self.get_device_status`、`self.audio_speaker.set_volume`、`self.reboot`、`self.upgrade_firmware` 等。

### 1.3 U8→U1 Edge-D UART 协议命令（`Protocol.cpp`，已验证）

U1 只解析以 `@` 前缀的命令行：

| 命令 | 行号 | 用途 |
|------|------|------|
| `@HOME` | 222 | 归位 |
| `@MOVE` | 243 | 单点移动 |
| `@PATH_BEGIN` | 336 | 路径开始 |
| `@PATH_SEG` | 358 | 路径分段 |
| `@PATH_END` | 410 | 路径结束 |

U8 侧由 `u1_protocol_client.SendU1ProtocolJson(...)` 生成并发送这些命令。

### 1.4 已存在的防呆/互斥机制（已验证）

| 机制 | 位置 | 状态 |
|------|------|------|
| UART 互斥锁 | `u1_protocol_client.h:102` `std::mutex uart_mutex_` | ✅ 已实现（保证单条 UART 指令原子） |
| Job 互斥锁 | `u1_protocol_client.h:103` `std::mutex job_mutex_` | ✅ 已实现 |
| OTA 状态拦截 | `dlc_motor_control_p1_ai_board.cc:271` `kDeviceStateUpgrading` → `E_DEVICE_UPDATING` | ✅ 已实现（升级中拒绝运动） |
| capability 归一化 | `NormalizeMotionCapabilityName`（`test_u8_protocol_logic.cpp` 覆盖） | ✅ 已实现 |

---

## 2. 关键缺口（P2 必须补）

### 2.1 缺口 A：无运动繁忙锁 `motion_busy_`

**事实：** `motion_executor.h` 当前只有执行方法（`ExecuteHomeWithTaskId` / `ExecuteMoveWithTaskId` / `RunPathWithTaskId` / `RunPath` 等），**没有** `motion_busy_` / `is_running` 标志位。

**风险：** `uart_mutex_` 只保证**单条** UART 指令原子，**不保证**一段 `PATH_BEGIN→PATH_SEG*→PATH_END` 序列的完整性。设备在线时，若多源（小智云链式调用 / 小程序 dispatch）在任务 A 执行中又下发任务 B，两段路径的 UART 指令会交错 → **U1 乱序执行或报错**。

**详细分析见** `lima-slimdown-design.md` §1.6.6。

### 2.2 缺口 B：无 `self.plotter.*` 高层工具

**事实：** 当前只有 `self.motor.*` 低层运动工具，**没有** `self.plotter.write_text` / `self.plotter.draw_generated`。

**影响：** 语音路径 A（纯 MCP）目前只能靠小智云 LLM 链式调用「服务端 `dlc.write_text` 返回 path → 设备端 `self.motor.run_path(path_json)`」。是否新增 `self.plotter.*` 取决于实现策略（见 §4）。

---

## 3. P2 固件改造设计（冻结）

### 3.1 层 1：固件端运动忙标志（必须，P2）

在 `motion_executor` 增加原子忙标志，运动类入口用 CAS + RAII 保护：

```cpp
// motion_executor.h — 新增私有成员
private:
    std::atomic<bool> motion_busy_{false};

// motion_executor.cc — RunPathWithTaskId / RunPath / ExecuteHome* / ExecuteMove* 开头
    bool expected = false;
    if (!motion_busy_.compare_exchange_strong(expected, true)) {
        return std::string("device is busy: a motion task is already running");
    }
    struct BusyGuard {
        std::atomic<bool>& flag;
        ~BusyGuard() { flag.store(false); }
    } guard{motion_busy_};
    // ... 原有 PATH_BEGIN/PATH_SEG/PATH_END 逻辑，异常/提前 return 时 guard 自动复位 ...
```

**加锁范围：**

| 方法 | 是否加 `motion_busy_` | 理由 |
|------|----------------------|------|
| `RunPathWithTaskId` / `RunPath` | ✅ 加 | 长序列路径，最需要保护 |
| `ExecuteHomeWithTaskId` / `ExecuteHomeCapability` | ✅ 加 | 归位期间不能插入新运动 |
| `ExecuteMoveWithTaskId` / `ExecuteMoveCapability` | ✅ 加 | 同上 |
| `ExecuteMoveRelWithTaskId` / `ExecuteMoveRelCapability` | ✅ 加 | 同上 |
| `ExecutePauseCapability` / `ExecuteResumeCapability` / `ExecuteStopCapability` | ❌ 不加 | pause/resume/stop 必须能在运动中调用 |

### 3.2 层 2：拒绝时的返回契约

设备忙时统一返回固定文案，供小智云 LLM 识别：

```text
"device is busy: a motion task is already running"
```

LLM 收到该文案 → 生成 TTS「绘图机正在忙，请稍等」。配合角色 prompt（存小智控制台）确保 LLM 不立即重试。

### 3.3 与服务端 pre-check 的分工

| 入口 | 防呆层 |
|------|--------|
| 小程序 / HTTP dispatch | 服务端 `dlc_core.dispatch` pre-check（`active_tasks_for_device` 非空 → 返回 `device_busy`） |
| 小智云链式调用固件高层 tool | 固件 `motion_busy_`（硬底线） |
| 设备离线 | 现有 FIFO 队列（`registry.get` 返回 None → 重入队），已安全 |

> **结论：** 服务端 pre-check 是体验优化（避免无效路径生成），固件 `motion_busy_` 是硬件安全底线。两层都要，P2 同时实现。

---

## 4. `self.plotter.*` 是否新增（策略选择，P1 决策 / P2 实现）

固件端是否新增 `self.plotter.write_text` / `self.plotter.draw_generated`，取决于语音路径 A 采用哪种实现策略：

| 策略 | 固件新增 tool | 执行链 | 优点 | 缺点 |
|------|--------------|--------|------|------|
| 策略一：设备端调 dlc_api | `self.plotter.write_text` / `self.plotter.draw_generated` | 固件 tool 内部 HTTP 调 `dlc_api` 生成路径 → 内部走 `RunPath` | 一次语音一个 tool，LLM 无需理解链式因果 | 固件需内置 HTTP client + token |
| 策略二：云端链式调用 | 无（复用 `self.motor.run_path`） | LLM 调服务端 `dlc.write_text` → 返回 path → LLM 调 `self.motor.run_path(path_json)` | 固件零新增 | 依赖 LLM 稳定链式调用（Q-01 待实测） |

**`draw_from_image` 固定走策略二**（需要 `image_url` 参数，固件不新增图片类高层 tool）。

> **Ponytail 决策建议：** 优先策略二（固件零改动，最省），仅当 Q-01 实测证明 LLM 链式调用不稳定时，才回退策略一新增 `self.plotter.*`。最终选择在 P1 依据 Q-01 实测结果冻结。

---

## 5. U1 端（Grbl）改造边界

**结论：U1 端本次基本不改。**

- `@HOME` / `@MOVE` / `@PATH_BEGIN` / `@PATH_SEG` / `@PATH_END` 协议已稳定。
- 机型配置 `dlc_motor_control_p1.yaml` / `dlc_motor_control_p1.h` 不动。
- P2 只需保证 U8 侧发送序列完整（靠 `motion_busy_`），U1 无需感知繁忙状态。
- 运动安全边界（工作区、feed 范围）由 U8 侧 `dlc_core.path_validator` + `run_path` feed 范围（1-20000）双重约束。

---

## 6. P2 固件验收标准

1. `motion_executor` 已加 `motion_busy_`，运动中下发新运动任务被拒绝并返回固定文案。
2. `pause` / `resume` / `stop` 在运动中仍可调用（不被 busy 锁挡住）。
3. 语音路径 A 策略最终选定（策略一或策略二），并有真机验证记录。
4. 真机至少跑通一条完整写字路径：语音 → 小智云 → MCP → U8 → U1 → 电机 → `DONE` 上报。
5. OTA 升级中运动任务仍被 `E_DEVICE_UPDATING` 拒绝（回归验证，不得破坏现有行为）。

> **真机验证硬规则：** 本地假设备验证不等于真机发布证据。涉及真实运动/激光/舵机时必须单独做硬件验证（见 `07-validation-and-acceptance.md`）。

---

## 7. 本分册与其它文档的关系

| 文档 | 关系 |
|------|------|
| `01-architecture.md` | 提供全链路时序与三种下发路径 |
| `02-service-refactor.md` | 提供 `dlc_core.dispatch` pre-check（服务端防呆层） |
| `04-miniprogram-refactor.md` | 小程序 dispatch 入口与固件防呆的配合 |
| `06-failure-and-safety.md` | 失败恢复、错误码、防呆完整闭环 |
| `08-open-questions.md` | Q-01（链式调用）、Q-08（motion_busy_）、Q-09（配网） |
