# 小智官方云 + DLC 核心：总体架构与责任边界

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`，以小智官方云承载语音/对话/LLM，以 DLC 核心承载写字/绘图/路径/设备控制。**
> 关联入口：`docs/xiaozhi-cloud/README.md`
> 关联路线图：`docs/xiaozhi-cloud/00-roadmap.md`
> 关联证据：`docs/xiaozhi-cloud/09-p0-evidence.md`
> 关联未决项：`docs/xiaozhi-cloud/08-open-questions.md`
> 总设计稿（逐步拆分中）：`docs/xiaozhi-cloud/lima-slimdown-design.md`

---

## 1. 本文件的角色

本文件是**架构分册**，只回答四个问题：

1. 系统分几层，每层是谁。
2. 各层责任边界在哪，谁不做什么。
3. 一次「写字/画画」请求怎么流过全链路。
4. 任务下发有哪几条路径，各自的适用与风险。

不在本文件展开的内容（放到对应分册）：

- 服务端模块/接口冻结细节 → `02-service-refactor.md`
- 固件端 tool 注册/防呆 → `03-firmware-refactor.md`
- 小程序端交互/配网 → `04-miniprogram-refactor.md`
- 双云部署/观测/回滚 → `05-deployment-and-ops.md`
- 失败恢复/安全边界 → `06-failure-and-safety.md`

---

## 2. 分层总览

系统分为 5 层，从上到下：

| 层 | 组件 | 归属 | 核心职责 |
|----|------|------|----------|
| L1 用户交互 | 语音（ESP32 U8）、微信小程序、HTTP 调试 | 产品前端 | 采集用户意图入口 |
| L2 云端对话 | 小智官方云 `xiaozhi.me` | 外部（不自维护） | 唤醒 / ASR / TTS / LLM / 意图识别 / MCP 调用 |
| L3 DLC 接入与核心 | `dlc_mcp` / `dlc_api` / `dlc_core` | 自研（产品核心资产） | 文字→路径 / SVG→路径 / 图片→路径 / 校验 / 下发 / 状态 |
| L4 U8 固件 | ESP32 U8（小智固件 + MCP Server） | 自研固件 | 接收路径 → Edge-D UART → U1；上报运动事件 |
| L5 U1 固件 | ESP32 U1（Grbl_Esp32） | 自研固件 | 解析 @JSON → 驱动电机/激光/舵机 |

**核心决策：L2 完全外包给小智官方云；L3 是必须留在自己手里的核心；L4/L5 是自研硬件闭环。**

---

## 3. 责任边界（谁做什么，谁不做什么）

### 3.1 小智官方云（L2）

**做：**
- 语音唤醒、ASR、TTS
- 普通对话与 LLM 推理
- 识别「写字/画画/控制」意图
- 通过 MCP `tools/call` 调用 DLC 工具与设备工具

**不做（也不应依赖它做）：**
- 不生成运动路径
- 不做路径安全校验
- 不理解 Grbl / UART / 机械边界
- 不持久化设备任务状态

### 3.2 DLC 核心（L3）

**做：**
- `dlc_mcp`：把 DLC 能力暴露为 MCP tool，桥接官方云
- `dlc_api`：HTTP 入口（小程序 / 内部调用 / 健康检查）
- `dlc_core`：纯算法与薄封装（文字→路径 / SVG→路径 / 图片→路径 / 校验 / 预设 / 状态聚合 / 下发）

**不做：**
- 不做 ASR/TTS/LLM
- 不做多后端 AI 路由平台那套（健康/预算/fallback/routing ML）
- 不在 `dlc_core` 里放网络 I/O（I/O 归 `dlc_api` / `dlc_mcp` / `dispatch`）

### 3.3 U8 固件（L4）

**做：**
- 注册设备端 MCP tool（`self.motor.run_path` 等）
- 接收路径 JSON，经 Edge-D UART 转给 U1
- 运动繁忙防呆（`motion_busy_`，见 `03-firmware-refactor.md`）
- 上报运动事件（done/failed/progress）

**不做：**
- 不生成路径（路径来自 L3）
- 不做复杂图像处理

### 3.4 U1 固件（L5）

**做：**
- 解析 `@JSON` 命令：HOME / MOVE / PATH_BEGIN / PATH_SEG / PATH_END
- 驱动电机/激光/舵机
- 返回执行结果

**不做：**
- 不联网，不认识 MCP，只认 UART 协议

---

## 4. 全链路架构图

```text
┌───────────────────────────────────────────────────────────────┐
│ L1 用户交互层                                                  │
│   语音(ESP32 U8)      微信小程序        HTTP 调试(curl)         │
└──────┬──────────────────┬──────────────────┬──────────────────┘
       │                  │                  │
       ▼                  │                  │
┌─────────────────────────┼──────────────────┼──────────────────┐
│ L2 小智官方云 xiaozhi.me │                  │                  │
│   唤醒→ASR→LLM→TTS       │                  │                  │
│   意图识别 → MCP tools/call                                    │
│   接入点 wss://api.xiaozhi.me/mcp/?token=<JWT>（模式 A）       │
└──────┬──────────────────┼──────────────────┼──────────────────┘
       │ MCP JSON-RPC 2.0  │ HTTPS            │ HTTPS
       ▼                   ▼                  ▼
┌───────────────────────────────────────────────────────────────┐
│ L3 DLC 核心                                                    │
│   dlc_mcp（模式 A 直连官方云 / 模式 B 自托管 endpoint-server）  │
│     tools: write_text / draw_generated / draw_from_image /     │
│            validate_path / get_device_status / knowledge        │
│   dlc_api（FastAPI）: /health /dlc/tasks/preview /dlc/tasks/dispatch /status │
│   dlc_core: text_to_path / svg_to_motion / image_to_path /     │
│             precheck / preset / optimizer / validator /         │
│             device_status / dispatch                            │
└──────────────────────────┬────────────────────────────────────┘
                           │ motion_task / run_path
                           ▼
┌───────────────────────────────────────────────────────────────┐
│ L4 ESP32 U8 固件（小智固件 + MCP Server）                      │
│   self.motor.run_path → U1 Protocol Client → Edge-D UART        │
└──────────────────────────┬────────────────────────────────────┘
                           │ Edge-D UART (@JSON\n)
                           ▼
┌───────────────────────────────────────────────────────────────┐
│ L5 ESP32 U1 固件（Grbl_Esp32）                                 │
│   解析 @JSON → HOME/MOVE/PATH_* → 电机/激光/舵机                │
└───────────────────────────────────────────────────────────────┘
```

---

## 5. 一次「写字」请求的完整时序

```text
用户: "写你好小智"

L1/L4 ESP32 U8
  → 语音唤醒 → ASR → 上送小智官方云

L2 小智官方云
  → LLM 识别意图 = 写字
  → MCP tools/call: dlc.write_text(device_id, text="你好")
     endpoint: wss://api.xiaozhi.me/mcp/?token=<JWT>（模式 A）

L3 dlc_mcp
  → 收到 tools/call
  → 经 dlc_api → dlc_core.text_to_path("你好")
  → dlc_core 路径校验（precheck / validate_path）
  → 返回 {status, task_id / path, preview}

L2 小智官方云
  → LLM 收到结果，TTS："好的，帮你写'你好'"
  → （路径 A）LLM 再调 self.motor.run_path(path_json)
     ※ 平台支持多轮 tool call；具体模型是否主动链式调用需 P0 实测（见 08-open-questions Q-01）

L4 U8
  → mcp_server 收到 self.motor.run_path
  → motion_busy_ 防呆检查
  → U1 Protocol Client → PATH_BEGIN / PATH_SEG / PATH_END

L5 U1 Grbl
  → 解析 @JSON → 驱动电机 → 返回 DONE

L4 U8
  → 上报 motion_event（done/failed/progress）到云 / 小程序
```

> 说明：P1 阶段 `dlc_api` 已实现 `/dlc/tasks/preview` 与 `/dlc/tasks/dispatch`，P0 的 `/write`、`/draw` 已删除。`dlc.write_text` / `dlc.draw_generated` 经 `dlc_api /dlc/tasks/dispatch` 进入 `dlc_core` 生成路径后下发，见 `02-service-refactor.md` 与 `10-p1-evidence.md`。

---

## 6. 三种任务下发路径

| 路径 | 触发源 | 通道 | 优势 | 风险/代价 |
|------|--------|------|------|-----------|
| A 纯 MCP | 小智云语音 | MCP `dlc.write_text` → 返回 path → 小智云调 `self.motor.run_path` | 全语音闭环，不依赖小程序 | 依赖 LLM 主动链式调用两个 tool（平台支持已确认，模型行为待 P0 实测） |
| B 小程序 HTTP | 小程序按钮 | HTTPS → `dlc_api /dlc/tasks/dispatch` → U8 WS/MQTT | 不依赖 LLM 链式行为，直接可控 | 需要用户打开小程序 |
| C 混合 | 小智云语音 + 小程序确认 | MCP 生成 path → 小程序预览 → 用户确认 → dispatch | 规避 LLM 理解偏差，带人工确认 | 多一步交互 |

### 6.1 平台能力已确认（证据链）

来自官方开源仓库 `xinnan-tech/xiaozhi-esp32-server`（自托管版，非官方云闭源代码）：

| 组件 | 位置 | 证据 |
|------|------|------|
| 递归深度控制 | `core/connection.py:941` | `MAX_DEPTH = 5` |
| 深度上限禁用 tools | `core/connection.py:944` | `if depth >= MAX_DEPTH: force_final_answer = True` |
| 服务端 MCP tool 返回 | `core/providers/tools/mcp_endpoint/mcp_endpoint_executor.py:53` | `ActionResponse(action=Action.REQLLM, ...)` |
| 设备端 MCP tool 返回 | `core/providers/tools/device_mcp/mcp_executor.py:53` | `ActionResponse(action=Action.REQLLM, ...)` |
| REQLLM 触发递归 | `core/connection.py:1270,1357` | 写入 `role="tool"` → `self.chat(None, depth=depth+1)` |

**结论：** 平台原生支持「服务端 tool 返回路径 → 写回对话 → 下一轮 LLM 调设备端 tool」的多轮链式调用。

### 6.2 唯一剩余不确定项

具体 LLM 模型（GLM/Qwen/豆包等）是否会在拿到 `dlc.write_text` 返回的路径后**主动决定**调用 `self.motor.run_path`，属于**模型行为**而非平台能力。这是 P0 实测项 Q-01（见 `08-open-questions.md`）。

**默认规避：** 若路径 A 实测不稳定，产品默认走路径 B 或 C（小程序 dispatch），不阻塞交付。

---

## 7. 关键架构约束

1. **DLC 核心不可外包**：文字→路径 / 校验 / Grbl 闭环必须自研，不能依赖云端。
2. **`dlc_core` 无网络 I/O**：保持纯算法可测；I/O 归 `dlc_api` / `dlc_mcp` / `dispatch`。
3. **路径安全在服务端定，在固件端复核**：`dlc_core` 生成即校验，U8 `motion_busy_` 防呆，双层保护。
4. **单机运动天然串行**：一台绘图机同时只执行一个任务；「高并发」指多用户/多设备并发，靠服务端水平扩展与 Redis 队列。
5. **未验证不写成事实**：涉及官方云 LLM 行为的结论必须回指 `08-open-questions.md`，不得当成既定事实实现。

---

## 8. 与总设计稿的关系

- 本文件从 `lima-slimdown-design.md` §2「系统架构」抽取并收敛，作为架构权威分册。
- 后续架构层面的变更以本文件为准；`lima-slimdown-design.md` 对应章节逐步降级为草稿。
- 模块/接口级细节不在此冻结，见 `02-service-refactor.md`。
