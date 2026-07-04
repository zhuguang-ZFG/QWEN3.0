# LiMa 瘦身工程设计文档：小智云 + DLC 绘图核心

> 日期：2026-07-05
> 状态：工程设计，待实现
> 作者：Kimi Code CLI
> 关联文档：
> - `docs/superpowers/specs/2026-07-04-xiaozhi-dlc-server-migration-design.md`（旧迁移设计，已被本文档取代）
> - `docs/xiaozhi-cloud/`（小智官方文档本地缓存）
> - 计划文件：`.kimi-code/plans/mister-miracle-captain-america-elektra.md`

---

## 1. 背景与动机

### 1.1 当前状态

LiMa（`D:/QWEN3.0`）已演进为 130,000+ 行的多后端 AI 路由 + 智能硬件云平台，包含：

- 170+ AI 后端路由 / 健康探测 / 预算 / fallback
- Chat Web / 官网 / docs-site / 三语言 SDK
- Provider automation / provider probe
- Semantic cache / session memory / learning loop
- Routing ML / context pipeline（17 模块）
- 设备网关 / 绘图 / 写字 / 语音 / 数字人
- Prometheus / Grafana 可观测体系
- Telegram 图库 / OTA 发布系统

实际产品只需要：**ESP32 写字机/绘图机**。

### 1.2 目标产品架构

```text
用户语音
  → ESP32 U8（小智固件）→ 小智官方云（xiaozhi.me）
      负责：唤醒 / ASR / TTS / 普通对话 / LLM 意图识别
      通过 MCP 协议调用工具
  → DLC 绘图服务（LiMa 收缩后的核心）
      负责：文字→路径 / SVG→路径 / 路径校验 / Grbl
  → U8 → Edge-D UART → U1 Grbl → 电机/激光
```

### 1.3 核心决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 对话/语音/LLM | 小智官方云（xiaozhi.me） | 基础额度免费、持续迭代、无需自维护 ASR/TTS/LLM（付费增值服务以官方公告为准） |
| 设备控制协议 | MCP（小智官方推荐） | JSON-RPC 2.0，官方云原生支持 |
| 外部 MCP 服务接入 | 模式 A：官方云直连 MCP 接入点（推荐）<br>模式 B：自托管 mcp-endpoint-server | 模式 A 无需自部署服务器，配置最简单；模式 B 适用于需要本地私有化部署的场景 |
| 绘图/写字核心 | 从 LiMa 抽取，做轻量服务 | 产品核心资产，不可外包给云 |
| 图库功能 | 保留 | 用户可能使用系统提供或用户上传的图片进行绘图；图库由 Telegram Bot 存储，LiMa 仅保存 file ID 和元数据 |
| LiMa 瘦身策略 | Strangler Fig | 先建新入口，再逐批删除旧系统 |

### 1.4 开发原则

本设计遵循仓库两级开发原则：

| 优先级 | 原则 | 文档 | 对本次瘦身的指导 |
|--------|------|------|------------------|
| 第一 | Ponytail「lazy senior dev」 | [`docs/AGENTS_PONYTAIL.md`](../AGENTS_PONYTAIL.md) | 能少写就少写；优先复用 GitHub/官方云高可靠实现；改固件/小程序前加载对应 skills；最小变更 |
| 第二 | SOLID + LoD + CRP + 清晰指令/上下文/工具接口/自动化验证 | [`docs/AGENTS_DESIGN_PRINCIPLES.md`](../AGENTS_DESIGN_PRINCIPLES.md) | `dlc_core` / `dlc_api` / `dlc_mcp` 按 SRP 拆分；新增能力通过 OCP 扩展；接口幂等可观测；改动必过测试/静态检查 |

**关键自检：**

- 小智官方云已免费提供的能力（ASR/TTS/LLM/普通对话），不再自维护。
- DLC 核心（文字→路径 / SVG→路径 / 路径校验 / Grbl）保持完整且内聚。
- 新增 MCP tool / HTTP API 遵循最小暴露原则。

### 1.5 云服务器职责分配

#### 现状回顾

| 服务器 | 当前角色 | 瘦身后的重新定位 |
|--------|----------|------------------|
| 阿里云 `47.112.162.80` | `chat.donglicao.com` 公网入口；运行 `lima-router-pilot`（匿名简单 chat） | 保留为 **public entry / edge**，承载 `dlc_api` / `dlc_mcp` 公网入口；chat/LLM 路由退役 |
| JDCloud `117.72.118.95` | primary `lima-router` compute；运行 MySQL/Redis/Prometheus/new-api/probe/worker | 转为 **backend / data / observability** 节点；保留 MySQL/Redis/Prometheus/后台任务；通过 Tailscale 与阿里云互联 |

#### 推荐分配

**Ponytail 应用：能少动就少动，优先复用现有 DNS/Tailscale 拓扑。**

| 服务器 | 新角色 | 运行服务 | 理由 |
|--------|--------|----------|------|
| 阿里云 `47.112.162.80` | Public entry / edge | nginx、`dlc_api`、`dlc_mcp`、TLS termination | 已有 `chat.donglicao.com` DNS 和稳定公网入口；DLC 作为新核心需要公网暴露 |
| JDCloud `117.72.118.95` | Backend / data / observability | MySQL、Redis、Prometheus、Grafana、probe browser、`jdcloud-worker`、可选 `dlc_api` hot-standby | 已有数据层和观测体系；内网通过 Tailscale 互联；domain policy 限制使其不适合直接作为公网入口 |

#### 网络拓扑

```text
Internet
   │
   ▼
chat.donglicao.com → 阿里云 47.112.162.80 (nginx :443)
   │
   ├─ /dlc/*            → dlc_api
   ├─ /device/v1/*      → dlc_api / 设备网关（按最终瘦身范围保留）
   └─ /health / metrics → dlc_api / 本地探针
   │
   Tailscale / 内网
   │
   ▼
JDCloud 117.72.118.95
   ├─ MySQL / Redis（dlc_api 持久化/缓存）
   ├─ Prometheus + Grafana（观测）
   ├─ probe browser / jdcloud-worker（后台任务）
   └─ dlc_api hot-standby（可选，双活或灾备）
```

#### 备选方案

| 方案 | 描述 | 适用场景 |
|------|------|----------|
| A（推荐） | 阿里云公网入口 + JDCloud 数据后台 | 默认；最小变更；复用现有 Tailscale 互联 |
| B | JDCloud 独揽全部，阿里云退役 | 需解决 JDCloud 公网 domain policy（如 Cloudflare Tunnel）；迁移风险高；仅在成本敏感时考虑 |
| C | 双云都跑完整 `dlc_api` 双活 | 可用性最高，但增加数据一致性和同步复杂度；仅在可用性要求极高时考虑 |

---

## 1.6 业务运营关键问题闭环

本节把产品/运维层面的 5 个关键疑问逐项给出工程结论，并明确落地到代码、配置或 MCP tool。

### 1.6.1 Telegram 能否作为图盘？

**结论：可以，且当前已实现。**

LiMa 的图库功能把 Telegram Bot API 当作对象存储后端使用：

- 图片字节上传到 Telegram，`file_id` 和元数据保存在本地 SQLite（`device_gateway/gallery_store.py`）。
- 下载时通过 `getFile` 换取临时 HTTPS URL（有效期数分钟），不长期占用本地磁盘。
- 代码位置：`routes/device_app_gallery.py`、`integrations/telegram_bot/client.py`。

**容量与速率限制（来自当前代码与 Telegram Bot API 文档）：**

| 限制项 | 当前值 | 说明 |
|--------|--------|------|
| Telegram 单文件上限 | 20 MB | `integrations/telegram_bot/constants.py`：`MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024` |
| Gallery 路由上传上限 | 10 MB | `routes/device_app_gallery.py`：`_MAX_UPLOAD_BYTES = 10 * 1024 * 1024` |
| 支持的 MIME | JPEG / PNG / WebP / GIF | `routes/device_app_gallery.py`：`_ALLOWED_CONTENT_TYPES` |
| 持久性 | file_id 持久；下载 URL 临时 | `client.py` 注释明确说明 |
| 并发 | 受 Telegram Bot API 全局速率限制 | 官方限制 30 msg/s（全局，不同会话）；同一会话 1 msg/s。LiMa 保守取 20 msg/s 作为安全阈值；突发高并发需 backoff |

**Ponytail 决策：** 既然当前已稳定运行、零额外成本，瘦身阶段保留 Telegram 图盘，不自行实现对象存储。

**Telegram 速率限制证据来源：**
- 官方限制：全局 30 msg/s（不同会话），同一会话 1 msg/s（[Telegram Bot API 文档](https://core.telegram.org/bots/api#handling-errors), [GitHub tdlib#3034](https://github.com/tdlib/td/issues/3034)）
- LiMa 保守取 20 msg/s 作为安全阈值，突发高并发需 backoff
- 图片上传走 `sendPhoto`/`sendDocument`，与消息共用配额

**未来迁移备选（P4 之后按需执行）：**

当图片量达到 Telegram 限制或需要 CDN 加速时，保留 `gallery_store` 接口不变，替换 `integrations/telegram_bot/client.py` 为 S3 / MinIO / Cloudflare R2 实现即可。`routes/device_app_gallery.py` 无需改动。

> **AGENTS.md 硬规则重申：** Telegram 通知通道已退役；图库存储后端不是通知通道，保留合法。

### 1.6.2 小智如何实时监控绘图机状态？

**结论：通过设备影子 + 任务状态 + 新增 MCP tool `dlc.get_device_status`。**

当前 LiMa 已维护三类状态：

1. **在线状态**：`device_gateway/sessions.py` 的 `registry` 记录设备的 WebSocket/MQTT 会话。
2. **设备影子**：`device_intelligence/shadow.py` 的 `shadow_store` 记录心跳、自检、最后运动事件、固件版本等。
3. **任务状态**：`device_gateway/store.py` / `redis_store.py` 的 `task_store` 记录任务的 `queued/dispatching/dispatched/accepted/running/done/failed` 等状态。

已有 REST 与 WebSocket 接口：

- `GET /device/v1/app/devices/{device_id}/status`（`routes/device_app_api.py:_build_device_status`）返回：
  ```json
  {
    "deviceId": "...",
    "online": true,
    "connectedAt": "...",
    "working": true,
    "activeTaskId": "task-000001",
    "firmwareVersion": "...",
    "protocolVersion": "...",
    "lastSeenAt": "..."
  }
  ```
- `/device/v1/app/devices/{device_id}/status/ws`（`routes/device_app_status_ws.py`）主动推送状态变化。

**为了让小智云 LLM 也能获取状态，新增服务端 MCP tool：**

```python
# dlc_mcp/server.py — 新增 tool
Tool(
    name="dlc.get_device_status",
    description="查询绘图机实时状态：在线/离线、是否工作中、当前任务ID、固件版本、最后运动事件。",
    inputSchema={
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备ID"},
        },
        "required": ["device_id"],
    },
)
```

**返回示例：**

```json
{
  "online": true,
  "working": true,
  "activeTaskId": "task-000042",
  "firmwareVersion": "u8-3.9.0",
  "lastMotionEvent": {"phase": "running", "progress": 37},
  "shadow": {"last_heartbeat_uptime_ms": 1234567, "self_check": {"ok": true}}
}
```

**典型语音交互：**

```text
用户：小智，绘图机在干嘛？
小智云 → MCP tools/call: dlc.get_device_status(device_id=...)
DLC  → 返回 {online: true, working: true, activeTaskId: "task-000042", lastMotionEvent: {phase: "running", progress: 37}}
小智云 → TTS："绘图机正在工作，当前任务编号 42，进度 37%。"
```

### 1.6.3 用户询问绘图机知识时，小智怎么回答？

**结论：优先使用小智官方云的角色配置（零代码）；复杂动态知识再走 MCP tool。**

小智官方控制台「智能体 → 配置角色」支持自定义 system prompt / 角色设定。把绘图机 FAQ、安全须知、操作示例写入角色 prompt 即可让 LLM 自然回答。

**角色 prompt 片段示例（存入小智控制台）：**

```text
你是一台智能绘图机的语音助手。绘图机由 ESP32 U8（小智固件）+ U1 Grbl 运动控制板组成，通过 UART 通信。

你可以帮用户：
- 语音控制绘图机写字、画画；
- 查询设备当前状态（在线/工作中/任务进度）——**必须调用 `dlc.get_device_status` 工具获取实时数据，不要自行推测或编造设备状态**；
- 解释常见故障与注意事项。

安全须知：
- 绘图机工作时不要触碰笔头/激光头；
- 必须先 HOME 归位才能开始任务；
- 路径越界、点数超限或未知指令会被拒绝执行；
- 长时间离线请检查 Wi-Fi 和电源。

控制指令（**必须调用对应工具，不要自行编造回复**）：
- 用户说"停止"→ 调用 `self.motor.stop` 工具
- 用户说"暂停"→ 调用 `self.motor.pause` 工具
- 用户说"继续/恢复"→ 调用 `self.motor.resume` 工具
- 用户说"归位/回零"→ 调用 `self.motor.home` 工具

常见故障：
- 不动作：检查 U1 电源、UART 接线、是否已 HOME；
- 笔画错位：重新 HOME，检查画布固定；
- 任务失败：可能是路径越界或机械卡死，小程序会推送失败原因。
```

**当知识需要动态查询时（例如查询某个具体错误码含义），新增 MCP tool：**

```python
# dlc_mcp/server.py — 新增 tool（可选）
Tool(
    name="dlc.get_plotter_knowledge",
    description="查询绘图机知识库：错误码含义、操作步骤、安全须知。",
    inputSchema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "enum": ["error_code", "safety", "operation", "hardware"]},
            "query": {"type": "string", "description": "具体问题或错误码"},
        },
        "required": ["topic", "query"],
    },
)
```

**Ponytail 决策：** 先最小化——用控制台角色 prompt 解决 80% 知识问答；只有 FAQ 无法覆盖的动态数据（错误码映射）才实现 MCP tool。

### 1.6.4 用户多起来后，能否支持高速并发？

**结论：服务端可水平扩展；单台绘图机物理上串行执行，并发指多用户/多设备并发。**

当前架构已经具备扩展基础：

| 组件 | 当前实现 | 扩展方式 |
|------|---------|---------|
| `dlc_api` | 无状态 FastAPI | 多实例 + nginx 负载均衡 |
| 任务队列 | `RedisDeviceTaskStore`（`device_gateway/redis_store.py`） | Redis 队列，原子 LMOVE / CAS |
| 设备状态 | `shadow_store`（内存，`threading.RLock`+`dict`，**进程内不跨实例共享**）+ `task_store`（Redis） | **P2 默认单实例部署**，零改动；未来水平扩展前必须先把 `shadow_store` 迁移到 Redis（见 §7 P2.4） |
| MQTT broker | 外部 broker（Mosquitto/EMQX） | broker 集群 |
| 数据库 | SQLite（图库元数据）/ MySQL | 图库元数据可切 MySQL |

**关键原子操作证据（来自 `device_gateway/redis_store.py`）：**

- `pop_pending_tasks` 使用 `LMOVE` 原子地把任务从 pending 队列移到 processing 队列，防止多进程重复消费。
- `record_motion_event` 使用 Lua 脚本（`device_gateway/redis_cas.py:append_event_atomic`）原子追加事件并更新状态。
- `increment_retry_count` / `reset_task_for_retry` 使用 CAS 保护，避免并发覆盖 `retry_count`。

**瓶颈点：**

- 单台绘图机一次只能执行一个运动任务，任务在设备侧天然串行。
- `dlc_api` 本身只负责生成路径和下发任务，不承担长时间 I/O，因此很容易水平扩展。

**默认部署（P2）：**

```text
阿里云 47.112.162.80：1 个 dlc_api 实例（nginx 反代到 127.0.0.1:8080）
JDCloud 117.72.118.95：Redis + MySQL + Prometheus
```

**后续扩展路径（P4 之后）：**

- `shadow_store` 从内存切到 Redis（触发条件：需要多实例水平扩展，见 §7 P2.4）；
- `gallery_store` 从 SQLite 切到 MySQL；
- 增加 `dlc_api` 实例数量（必须先完成 shadow_store Redis 化）。

> **P2 部署策略：** `device_intelligence/shadow.py` 的 `shadow_store` 当前使用 `threading.RLock` + `dict` 内存存储，**多 `dlc_api` 实例间不共享**。P2 **默认采用单实例部署**，无需迁移。若后续需要 2+ 实例水平扩展，必须先完成 `shadow_store → Redis` 迁移（§7 P2.4）。单实例部署下设备状态查询一致。

### 1.6.5 任务失败怎么处理？

**结论：状态机 + 自动重试 + 死信 + 多渠道通知。**

**任务生命周期（已落实在 `device_gateway/protocol.py` 与 `device_gateway/store.py`）：**

```text
queued → dispatching → dispatched → accepted → running → done / failed / cancelled / rejected / stopped
```

**失败处理流程：**

**阶段 A：下发阶段失败（`dispatching` → `dispatched`）**

1. **检测**：`device_gateway/redis_store.py` 的 `dispatch_task` 超时或 MQTT/WS 发送失败。
2. **恢复**：`device_gateway/task_events.py` 检测 `dispatched` 状态超时（配置 `dispatch_timeout`，默认 30s），标记为 `failed`。
3. **通知**：同阶段 B 的通知链路。

**阶段 B：运行阶段失败（`running` → `failed`）**

4. **检测**：设备上报 `motion_event` phase=`failed`，并携带 `error` / `error_code`。
2. **恢复决策**：`device_gateway/task_events.py:_recovery_for_event` 调用 `device_intelligence/recovery.py` 的 `recovery_action()` 与 `should_retry()`。
3. **自动重试**：若错误码允许重试且未达上限，`task_store.reset_task_for_retry()` 递增 `retry_count` 并重新入队（`enqueue_pending_task`）。
4. **死信**：重试耗尽或不可重试时，`abandon_processing_task()` 标记为 `dead_letter`；`artifact_store.put_artifact(task_id=task_id, artifact_type="terminal_result", retention_days=90)` 将终端事件落盘保留 90 天。
5. **通知**：`device_logic/notifications.py` 通过微信小程序订阅消息推送 `task_completed` / `task_failed` / `device_offline`。
6. **记忆学习**：`device_memory/extractor.py` 从终端事件提取故障记忆，用于后续故障排查建议。

**错误码与恢复策略示例（基于 `device_intelligence/recovery.py` 现有 + 设计新增）：**

| 错误码 | 含义 | 默认动作 | 重试上限 | 来源 |
|--------|------|---------|---------|------|
| `E_NOT_HOMED` | 未归位 | stop + 语音提示"请先归位" | 0 | 现有 ✅ |
| `E_MISSING_PATH` | 设备未收到路径数据 | retry | 3 | 现有 ✅ |
| `E_LIMIT` | 触发限位保护 | retry | 1 | 现有 ✅ |
| `E_UART_TIMEOUT` | U1 串口响应超时 | retry | 2 | 现有 ✅ |
| `E_ESTOP` | 急停触发 | stop + 等待人工检查 | 0 | 现有 ✅ |
| `E_PATH_OUT_OF_BOUNDS` | 路径越界 | stop + 拒绝执行 | 0 | **设计新增**（P1 实现时添加到 recovery.py） |
| `E_UNKNOWN` | 未知错误 | stop + 等待人工检查 | 0 | **设计新增**（P1 实现时添加到 recovery.py） |

**用户感知：**

- **语音**：小智云 LLM 根据 `dlc.get_device_status` 或失败通知生成 TTS，例如"任务执行失败，电机堵转，已尝试重试一次"。
- **小程序**：订阅消息推送 + 任务详情页显示失败原因与重试记录。
- **运维**：Prometheus 指标 + `device_ledger` 审计日志用于离线分析。

**Ponytail 决策：** 复用现有 `device_intelligence/recovery.py` + `device_logic/notifications.py`，不重新发明通知通道；失败处理逻辑在瘦身阶段保持完整。

### 1.6.6 设备运行中防呆机制（anti-foolhardiness）

> **场景：** 用户对正在画画的小智说"再画一颗星星"或"写字你好"——设备正在执行任务 A，此时 LLM 又调用了 `dlc.write_text` 或 `self.motor.run_path` 下发任务 B。会发生什么？

**当前代码的多层防呆分析：**

| 层级 | 机制 | 代码位置 | 现有状态 |
|------|------|---------|---------|
| **固件 UART 互斥** | `U1ProtocolClient` 持有 `uart_mutex_` + `job_mutex_`，保证同一时刻只有一条 UART 指令在跟 U1 通信 | `u1_protocol_client.h:102-103` | ✅ 已实现 |
| **固件 OTA 拦截** | 设备在 `kDeviceStateUpgrading` 状态时拒绝一切运动任务，返回 `E_DEVICE_UPDATING` | `dlc_motor_control_p1_ai_board.cc:271-277` | ✅ 已实现 |
| **服务端任务队列** | `task_store` 用 `LMOVE` 原子队列管理 pending→processing→done 状态，任务按 FIFO 顺序逐个下发到设备 | `device_gateway/redis_store.py` | ✅ 已实现 |
| **服务端 dispatch 串行** | `dispatch_task_to_session` 通过 `session.send_json(task)` 逐条发，设备 WS 接收后逐条处理 | `device_gateway_dispatch.py:108-137` | ✅ 已实现 |
| **固件 device_state** | 小智设备状态机（`kDeviceStateIdle/Listening/Speaking`）控制语音交互流程，不影响运动执行 | `device_state.h` | ✅ 已实现 |

**⚠ 关键缺口——固件端无运动繁忙状态锁：**

当前 `MotionExecutor` **没有** `is_busy` / `is_running` 标志位或互斥锁来阻止"运动任务正在进行中时接受新任务"。分析：

| 可能场景 | 用户体验 | 后果 |
|---------|---------|------|
| 小智 LLM 在设备执行 A 时调用 `self.motor.run_path(B)` | 任务 B 的 PATH_BEGIN 指令直接发到 UART，与 A 的指令交错 | **U1 乱序执行或报错**——`uart_mutex_` 只保证单条原子性，不保证路径序列完整性 |
| 小智 LLM 调用 `self.plotter.write_text(B)` | 同上，`PostDlcApi` 不阻塞，`RunPath` 立即执行 | **同上** |
| 小程序按下"一键写字" | HTTP `/dlc/tasks/dispatch` → `send_json(task)` → 设备 WS 收到→ 直接处理 | **同上** |
| 设备掉线时小智说"写字你好" | `dlc_api` 生路径成功，`dispatch_task_to_session` 检查 `registry.get(device_id)` 返回 None → 重入队，等设备重连后下发 | ✅ 安全（已有 FIFO 队列保护） |

**结论：UART 互斥锁保证单条指令原子但无法保证路径序列完整性；设备在线时多源并发的运动任务可能交错。**

**防呆方案设计（P1 固件端 + 服务端双层）：**

#### 层 1：固件端运动忙标志（必须，P1）

```cpp
// motion_executor.h — 新增
private:
    std::atomic<bool> motion_busy_{false};

// motion_executor.cc — RunPathWithTaskId 开头
ReturnValue MotionExecutor::RunPathWithTaskId(...) {
    // 防呆：运动忙时拒绝新任务
    bool expected = false;
    if (!motion_busy_.compare_exchange_strong(expected, true)) {
        return std::string("device is busy: a motion task is already running");
    }
    // ... 原有 PATH_BEGIN/PATH_SEG/PATH_END 逻辑 ...
    // 用 RAII 确保异常退出时也复位
    struct BusyGuard {
        std::atomic<bool>& flag;
        ~BusyGuard() { flag.store(false); }
    } guard{motion_busy_};

    // ... 正常执行 ...
    // guard 析构时自动复位 motion_busy_ = false
}
```

同理在 `ExecuteHomeWithTaskId`、`ExecuteMoveWithTaskId`、`ExecuteMoveRelWithTaskId` 也加 `motion_busy_` 检查。

`ExecutePauseCapability`、`ExecuteResumeCapability`、`ExecuteStopCapability` **不加** busy 检查（pause/resume/stop 可以在运动中调用）。

#### 层 2：服务端 pre-check + LLM 角色 prompt 指令（推荐，P1，仅覆盖 dispatch 路径）

```python
# dlc_core/dispatch.py — 下发前检查（仅 HTTP dispatch / task_store 路径生效）
async def dispatch_task(device_id: str, task: dict, *, channel: str = "mqtt") -> dict:
    # 防呆：检查设备是否已有活跃任务
    active = task_store.active_tasks_for_device(device_id)
    if active:
        return {"task_id": "", "status": "rejected", "reason": "device_busy",
                "active_task_id": active[0].get("task_id")}
    # ... 正常下发 ...
```

```python
# dlc_mcp/server.py — dispatch 类返回中包含建议
# 如果设备忙，返回 {status: "device_busy", active_task_id: "task-xxx", suggestion: "请先等待当前任务完成"}
# LLM 看到 device_busy 后自然对用户说"绘图机正在忙，请稍等"
```

角色 prompt 追加（存入小智控制台）：

```text
注意：如果用户发出的写字/绘图请求被返回 device_busy，请告知用户"绘图机正在执行上一个任务，请稍等"，不要重复尝试下发。
```

#### 层 3：固件端 MCP tool 拒绝响应（可选，P2+，覆盖本地高层 tool / 低层执行 tool）

当固件端 `self.plotter.write_text` / `self.plotter.draw_generated` / `self.motor.run_path` 因 motion_busy 返回错误时：
- 小智云 LLM 收到 `"device is busy: a motion task is already running"` → 生成 TTS"绘图机正在忙，请稍等"
- 角色 prompt 确保 LLM 不立即重试（见层 2 prompt 补充）

**防呆流程闭环图（按入口区分）：**

```text
入口 A：小程序 / HTTP dispatch
  用户点击一键写字 / 画图
    ↓
  dlc_core.dispatch_task
    ↓
  [服务端 pre-check]
    设备忙 → 返回 device_busy → 小程序提示稍后重试
    空闲   → 正常下发到设备

入口 B：小智云调用固件高层 tool
  用户说话 "再画一颗星星"
    ↓
  小智云 LLM → self.plotter.write_text(text="星星")
    ↓
  固件内部调 dlc_api 生成路径
    ↓
  [固件 motion_busy_]
    运动中 → 返回 "device is busy"
    空闲   → 正常执行
    ↓
  小智云 LLM 生成 TTS: "绘图机正在执行上一个任务，请稍等"
```

**拒绝时的错误返回（非运动安全拒绝，是排队拒绝）：**

| 错误状态 | 返回给 LLM/小程序 | 用户体验 |
|---------|------------------|---------|
| 固件 motion_busy | `"device is busy: a motion task is already running"` | LLM TTS"绘图机正在忙" |
| 服务端 active_task | `{"status": "rejected", "reason": "device_busy", "active_task_id": "..."}` | LLM TTS"正在执行任务 X，请稍等" |

> **Ponytail 决策：** 层 1（固件 `motion_busy_`）是必须的硬件安全底线；层 2（服务端 pre-check + 角色 prompt）是用户体验优化（避免无效路径生成）。P1 同时实现。层 3 依赖层 1 的返回值自然实现，无额外工作。

---

## 2. 系统架构

### 2.1 全链路架构

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         用户交互层                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                            │
│  │ 语音交互  │  │ 小程序UI  │  │ HTTP调试  │                            │
│  │ (ESP32)  │  │ (微信小程序)│  │ (curl等) │                            │
│  └────┬─────┘  └─────┬────┘  └─────┬────┘                            │
│       │               │              │                                │
└───────┼───────────────┼──────────────┼────────────────────────────────┘
        │               │              │
        ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    小智官方云（xiaozhi.me）                           │
│  唤醒→ASR→LLM→TTS 闭环                                              │
│  LLM 识别"写字/画画"意图 → MCP tools/call                             │
│  接入点：wss://api.xiaozhi.me/mcp/?token=<JWT>（模式 A）             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ MCP JSON-RPC 2.0 over WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    dlc_mcp / mcp_pipe（模式 A/B）                     │
│  模式 A：直连 api.xiaozhi.me（官方云 MCP 接入点）                     │
│  模式 B：连自托管 mcp-endpoint-server                                 │
│  注册自定义 MCP tool：write_text / draw_generated / draw_from_image /  │
│  get_device_status / get_plotter_knowledge / validate_path              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ dlc.write_text   │ │ dlc.draw_generated │ │dlc.validate_path │
│  (服务端MCP tool)  │ │  (服务端MCP tool)  │ │    (服务端tool)    │
└───────┬──────────┘ └─────────┬────────┘ └────────┬─────────┘
        │                     │
        │  dlc_api (FastAPI)   │
        │  /dlc/tasks/preview  │
        │  /dlc/tasks/dispatch │
        │  /dlc/devices/{id}/status │
        └──────────┬───────────┘
                   │
        ┌──────────▼───────────┐
        │    dlc_core          │
        │  text_to_path         │
        │  svg_path_to_motion   │
        │  image_to_path        │
        │  precheck_path        │
        │  preset_shapes        │
        │  path_optimizer       │
        │  safety_validator     │
        │  device_status        │
        │  knowledge            │
        └──────────┬───────────┘
                   │ motion_task / run_path
                   ▼
        ┌──────────────────────────────────────────────┐
        │           dlc_dispatch                        │
        │  方式A: MCP → 设备端 self.motor.run_path    │
        │  方式B: HTTP  → dlc_api → U8 WS/MQTT          │
        │  方式C: 小程序  → v2SubmitTask → LiMa → U8     │
        └──────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ESP32 U8 固件                                     │
│  MCP Server（mcp_server.cc）                                         │
│  注册 self.motor.run_path 工具                                      │
│  接收 path JSON → U1 Protocol Client → UART                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ Edge-D UART (@JSON\n)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ESP32 U1 固件（Grbl_Esp32）                      │
│  Protocol.cpp 解析 @JSON 命令                                        │
│  HOME / MOVE / PATH_BEGIN / PATH_SEG / PATH_END                      │
│  驱动电机/激光/舵机                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 MCP 工具调用流程（时序图）

```text
用户: "写你好小智"

ESP32 U8
  → [语音唤醒] → [ASR] → 小智云（xiaozhi.me）
  → 小智云 LLM 识别意图 → "写字"
  → 小智云 MCP tools/call: dlc.write_text(text="你好")
     WebSocket endpoint: wss://api.xiaozhi.me/mcp/?token=<JWT>（模式 A）
     或经自托管 mcp-endpoint-server（模式 B）

dlc_mcp（dlc_mcp_server + mcp_pipe 接入器）
  → 收到 tools/call
  → dlc_core.text_to_path("你好")
  → dlc_core.precheck_path(path)  ← 安全校验
  → 返回 {path: [...], preview_svg: "...", width, height}

小智云
  → 收到 dlc.write_text 结果
  → LLM 生成回复: "好的，我帮你写'你好'两个字"
  → TTS 语音播报
  → 通过 MCP 调用 self.motor.run_path(path_json)
     （自托管服务器架构支持多轮 tool call：MAX_DEPTH=5 + chat(depth+1)；
      官方云大概率一致，但 LLM 实际行为仍需 P0 实测确认）

ESP32 U8
  → mcp_server 收到 tools/call: self.motor.run_path
  → motion_executor.RunPath(path_json, feed)
  → u1_protocol_client.SendU1ProtocolJson(PATH_BEGIN + PATH_SEG + PATH_END)
  → U1 执行运动

U1 Grbl
  → 解析 @JSON 命令
  → 驱动电机
  → 返回 {"result":"DONE"}

U8
  → motion_event_emitter.EmitDoneOrFailed
  → 上报事件到小智云/小程序
```

### 2.3 三种任务下发路径

| 路径 | 来源 | 通道 | 优势 | 劣势 |
|------|------|------|------|------|
| **A. 纯 MCP** | 小智云语音 | MCP → dlc.write_text → 返回 path → 小智云调 self.motor.run_path | 全语音闭环，无需小程序 | 依赖 LLM 理解两个 tool 的因果关系并主动连续调用；自托管服务器代码已支持多轮 tool call，官方云大概率一致，但 P0 仍需实测确认 |
| **B. 小程序 HTTP** | 小程序按钮 | HTTPS → dlc_api/dlc/tasks/dispatch → U8 WS/MQTT | 不依赖小智云 LLM 链式行为，直接控制 | 需要用户打开小程序 |
| **C. 混合** | 小智云语音 | MCP → dlc.write_text 返回 path → 小智云回复"已生成" + 小程序展示预览 → 用户确认后小程序 dispatch | 语音 + 手动确认，规避 LLM 理解偏差风险 | 多一步交互 |

**路径 A 的代码证据（来自官方仓库 `xinnan-tech/xiaozhi-esp32-server`）：**

- 文件：`main/xiaozhi-server/core/connection.py`
- 关键机制：
  1. `MAX_DEPTH = 5`：服务器允许最多 5 层工具调用递归。
  2. `_handle_function_result()` 将 `Action.REQLLM` 的工具结果以 `role="tool"` 写回对话历史。
  3. 随后调用 `self.chat(None, depth=depth + 1)`，让 LLM 基于工具结果再次决策。
  4. 这意味着：只要 `dlc.write_text` 返回 `{path: [...]}`，LLM 在下一轮中**可以**调用 `self.motor.run_path(path_json=...)`。

**结论：** 自托管 `xiaozhi-esp32-server` 的架构原生支持多轮 tool call 链式调用；`xiaozhi.me` 官方云作为同一团队运营的闭源服务，大概率复用同一架构，但仍需在 P0 用真实官方云账号实测确认（因为无法直接读取官方云代码）。若路径 A 实测失败，则默认采用路径 B 或 C。

**链条调用代码证据链（已在官方仓库 `xinnan-tech/xiaozhi-esp32-server` 确认）：**

| 组件 | 文件 | 证据 |
|------|------|------|
| 递归深度控制 | `connection.py:941` | `MAX_DEPTH = 5` |
| 深度达上限时禁用 tools | `connection.py:944` | `if depth >= MAX_DEPTH: force_final_answer = True` → 不传入 functions → LLM 必须直接回答 |
| 服务端 MCP tool 返回 Action | `core/providers/tools/mcp_endpoint/mcp_endpoint_executor.py:53` | `return ActionResponse(action=Action.REQLLM, result=str(result))` |
| 设备端 MCP tool 返回 Action | `core/providers/tools/device_mcp/mcp_executor.py:53` | `return ActionResponse(action=Action.REQLLM, result=str(result))` |
| REQLLM 触发递归 | `connection.py:1270,1357` | `elif result.action == Action.REQLLM:` → 写入 `role="tool"` 消息 → `self.chat(None, depth=depth + 1)` |
| tool_call 检测 | `connection.py:1095,1183` | `if tool_call_flag:` → 并行调度 `func_handler.handle_llm_function_call` → 收集 results → `_handle_function_result(tool_results, depth=depth)` |

**平台能力已确认：** 服务端 MCP tool（`dlc.write_text` 返回 `Action.REQLLM`）→ `_handle_function_result` 写入 `role="tool"` → `chat(depth+1)` → LLM 在下一轮看到路径数据 → **可以**调用设备端 MCP tool（`self.motor.run_path`，同样返回 `Action.REQLLM`）→ 再次 `chat(depth+1)` → LLM 生成最终语音回复。

**唯一剩余不确定项（已从"平台能力不确定"降级为"模型行为不确定"）：** 具体 LLM 模型（如 GLM/Qwen/GPT）是否会在拿到 `dlc.write_text` 返回的路径 JSON 后**主动决定**调用 `self.motor.run_path`，取决于模型的 function-calling 推理能力，而非平台是否支持。P0 实测验证的是模型行为，而非平台能力。

固件端必须实现 `self.plotter.write_text` / `self.plotter.draw_generated`：
- 路径 A（纯 MCP）+ 实现策略二（云端链式调用）：由小智云 LLM 直接调用 `self.plotter.write_text` / `self.plotter.draw_generated`，固件内部调 dlc_api 生成并执行路径；
- 路径 A（纯 MCP）+ 实现策略一（设备端调 dlc_api）：`self.plotter.write_text` / `self.plotter.draw_generated` 是对低层执行 tool `self.motor.run_path` 的高层封装；
- 路径 B/C：小程序走 HTTP dispatch，不调用固件 MCP 高层 tool。

**图库图片矢量化（`draw_from_image`）的固件端处理：**

`dlc.draw_from_image` 是服务端 MCP tool，返回路径 JSON 后由 LLM 通过 `self.motor.run_path` 执行（实现策略二）。由于图片矢量化需要传入 `image_url` 参数，固件端**不新增** `self.plotter.draw_from_image` 或其它高层图片 tool，执行路径如下：

| 实现策略 | 固件端 tool | 执行链 |
|---------|-----------|--------|
| 策略一（设备端调 dlc_api） | 无 | 不适用于 draw_from_image（需要 image_url） |
| 策略二（云端链式调用） | `self.motor.run_path` 接受 path_json | LLM 调 `dlc.draw_from_image` → 返回 path → LLM 调 `self.motor.run_path(path_json)` |
| 路径 B/C（小程序） | 不涉及固件 MCP tool | 小程序直接调 `/dlc/tasks/dispatch` `type=draw_from_image` → dlc_api 生成路径 → 下发到设备 |

> **结论：** `draw_from_image` 的语音路径走策略二（LLM 链式调用 `dlc.draw_from_image` → `self.motor.run_path`），固件端无需新增图片类高层 tool。小程序路径走 HTTP dispatch，不经过 LLM。

---

## 3. 服务端改造（LiMa → DLC 核心）

### 3.1 新目录结构

```text
D:/QWEN3.0/
├── dlc_core/                    ← 绘图核心库（纯路径算法 + 薄封装，不含网络 I/O）
│   ├── __init__.py
│   ├── intent.py                 # 意图解析（从 device_gateway/intent.py 迁移）
│   ├── task_model.py             # 任务模型（从 device_gateway/task_creation.py 精简）
│   ├── write.py                  # 写字处理（从 device_gateway/device_write_handler.py 迁移）
│   ├── draw.py                   # 绘图处理：draw_generated（提示词/预设） + draw_from_image（图库图片矢量化）
│   ├── presets.py                # 预设图形（从 device_draw_handler.py 提取）
│   ├── path_pipeline.py          # 路径管线（从 device_gateway/path_pipeline.py 迁移）
│   ├── path_validator.py         # 路径校验（从 device_gateway/path_validator.py 迁移）
│   ├── safety.py                 # 安全边界（从 device_gateway/safety.py 迁移）
│   ├── preview.py                # SVG 预览生成
│   ├── dispatch.py               # 任务下发（MQTT/WS/HTTP）
│   ├── profiles.py               # 设备尺寸/约束（从 device_gateway/profiles.py 迁移）
│   ├── device_status.py          # 设备状态聚合（registry + task_store + shadow_store）
│   └── knowledge.py              # 绘图机知识库（可选；优先使用小智控制台角色 prompt）
├── dlc_api/                      ← 轻量 HTTP 服务
│   ├── __init__.py
│   ├── app.py                    # FastAPI minimal app
│   └── routes.py                 # /health, /dlc/tasks/*, /dlc/devices/{id}/status, /dlc/knowledge
├── dlc_mcp/                      ← MCP Server + 接入器
│   ├── __init__.py
│   ├── server.py                 # MCP tools: write_text / draw_generated / draw_from_image / validate_path / get_device_status / get_plotter_knowledge / dispatch_task
│   ├── schemas.py                # Tool 参数 schema
│   └── mcp_pipe.py               # MCP 接入器：模式 A 直连 api.xiaozhi.me；模式 B 接入自托管 mcp-endpoint-server
├── xiaozhi_drawing/              ← 绘图算法库（保留，dlc_core 依赖）
│   └── *.py                      # 13 个文件，不变
├── server.py                     ← 旧入口（降级为 legacy_lima，P4 删除）
├── server_dlc.py                 ← 新生产入口（P2 新增）
├── esp32S_XYZ/                   ← 固件 + 小程序子模块
└── docs/xiaozhi-cloud/           ← 小智官方文档缓存
```

### 3.2 dlc_core 接口定义

```python
# dlc_core/intent.py
def parse_intent(text: str) -> dict:
    """解析文本意图，返回 {capability, params, source, confidence, explanation}.

    Phase 1 facade 实现：from device_gateway.intent import resolve_voice_task as parse_intent
    capability: write_text | draw_generated | home | pause | resume | stop | move_abs | move_rel | run_path
    """


# 底层解析器（从 device_gateway/intent.py 迁移后保留为内部函数）
def parse_command(text: str) -> dict:
    """确定性正则解析，返回 {capability, params, source, confidence, explanation}."""


def resolve_voice_task(text: str) -> dict:
    """包装 parse_command，保留低置信度回退并可选 LLM replan。"""

# dlc_core/write.py
async def handle_write(
    text: str,
    *,
    font_style: str = "default",
    size: str = "medium",
    device_id: str | None = None,
) -> dict:
    """写字处理，返回 {status, path_data, preview_svg, width, height, model, error}."""

# dlc_core/draw.py
async def handle_draw(
    prompt: str,
    *,
    device_id: str | None = None,
    allow_dashscope: bool = False,
) -> dict:
    """提示词/预设绘图处理，返回 {status, svg_path, preview_svg, width, height, model, error}.

    allow_dashscope: 是否允许调用 DashScope 文生图。MCP tool / 固件调用默认 False；
                     小程序 HTTP 路径可设为 True，保留 AI 生图能力。
    """

async def handle_draw_from_image(
    image_url: str,
    *,
    device_id: str | None = None,
    skeletonize: bool = True,
) -> dict:
    """图片矢量化绘图处理。输入图片 URL，返回 {status, svg_path, preview_svg, width, height, model, error}.

    依赖 xiaozhi_drawing.svg_converter.SVGConverter 将图片转为 SVG 路径。
    图库上传/管理仍由 routes/device_app_gallery.py + integrations/telegram_bot/client.py 提供。

    **⚠ Telegram 临时 URL 时效问题：** Telegram `getFile` 返回的下载 URL 有效期约 5-10 分钟。
    如果 dlc_api 收到 draw_from_image 请求后异步排队，到矢量化时 URL 可能已过期。
    本函数收到请求时必须**立即下载图片到本地临时文件**（`/tmp/dlc_uploads/`），后续矢量化读本地文件。
    不依赖远程 URL 延迟读取。本地临时文件处理完后删除。
    """

# dlc_core/path_pipeline.py
def text_to_path(text: str, origin_x: float = 5, origin_y: float = 20, scale: float = 2) -> list[dict]:
    """文字 → 运动路径点列表 [{x, y, z}]（原 device_gateway/path_pipeline.py）。"""

# dlc_core/svg_parser.py（从 device_gateway/svg_parser.py 迁移）
def svg_path_to_motion(d_string: str, *, max_points: int = 2000) -> list[dict]:
    """SVG d-string → 原始运动路径点列表。

    `max_points=2000` 是解析/采样阶段上限，不是最终设备下发上限。
    真正允许单次下发到设备的安全上限由 `MAX_PATH_POINTS = 200` 决定。
    若解析结果 >200 点，必须在 `path_optimizer` / `dispatch` 前做压缩、抽稀或分片，保证单 task ≤200 点。
    `draw_from_image` 若超出 200 点，不得直接下发，必须：
    1. 压缩到 ≤200 点；或
    2. 分片为多个 sequential tasks；或
    3. 直接返回 422 / timeout，提示用户换更简单图片。
    """

# dlc_core/path_pipeline.py
def precheck_draw_motion_path(d_string: str) -> str | None:
    """运动边界预校验，返回错误消息或 None。"""

# dlc_core/path_validator.py
def validate_path(path: list[dict], *, workspace: dict | None = None) -> dict:
    """路径安全校验，返回 {ok, errors, warnings}。"""

# dlc_core/safety.py
DEFAULT_WORKSPACE_MM = {"x": 100.0, "y": 100.0, "z": 20.0}
# 注意：当前代码中 MAX_PATH_POINTS 定义在 device_gateway/path_data.py (=200) 和
# device_gateway/path_validator.py (=200)，而 device_gateway/safety.py 另有一个
# MAX_POINTS = 128。P3 迁移时需把运动安全边界统一收敛到 dlc_core， authoritative
# 值采用 200，并删除旧模块中的重复/冲突常量。
MAX_PATH_POINTS = 200

# dlc_core/dispatch.py
async def dispatch_task(device_id: str, task: dict, *, channel: str = "mqtt") -> dict:
    """下发任务到设备，返回 {task_id, status}。"""

# dlc_core/device_status.py
async def get_device_status(device_id: str) -> dict:
    """查询设备实时状态。

    聚合：registry 在线状态、active_tasks_for_device、shadow_store.snapshot。
    返回 {online, working, active_task_id, firmware_version, last_seen_at, shadow}。
    """

# dlc_core/knowledge.py
def get_plotter_knowledge(topic: str, query: str) -> dict:
    """查询绘图机知识库，返回 {topic, query, answer, source}。"""

# dlc_core/task_model.py
def intent_to_motion_task(intent: dict, device_id: str) -> dict:
    """意图 → motion_task 结构。"""
```

### 3.3 dlc_api 路由定义

```python
# dlc_api/routes.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "service": "dlc-drawing", "version": "1.0.0"}

# PreviewRequest.type: Literal["write_text", "draw_generated", "draw_from_image"]
# PreviewRequest.allow_dashscope: bool = False  # 仅 type=draw_generated 时生效；小程序可设 True
@router.post("/dlc/tasks/preview")
async def preview_task(body: PreviewRequest, token: str = Depends(verify_dlc_api_token)):
    """预览任务路径，不实际下发。支持写字、提示词绘图、图片矢量化绘图。

    type=draw_generated 时：
    - 固件/MCP 内部调用 allow_dashscope=False（仅本地预设/字体）
    - 小程序 HTTP 调用可设 allow_dashscope=True（保留 DashScope AI 生图）
    """
    # → dlc_core.handle_write / handle_draw / handle_draw_from_image / precheck_path
    return {"preview_svg": "...", "path": [...], "width": ..., "height": ...}

@router.post("/dlc/tasks/validate")
async def validate_task(body: ValidateRequest, token: str = Depends(verify_dlc_api_token)):
    """对已有路径做二次安全校验（固件端可选调用）。"""
    # → dlc_core.validate_path
    return {"ok": True/False, "errors": [...]}

# DispatchRequest.type: Literal["write_text", "draw_generated", "draw_from_image"]
# DispatchRequest.allow_dashscope: bool = False  # 仅 type=draw_generated 时生效；小程序可设 True
@router.post("/dlc/tasks/dispatch")
async def dispatch_task(body: DispatchRequest, token: str = Depends(verify_dlc_api_token)):
    # 鉴权：复用 access_guard 的 device token 机制，防止未授权下发运动指令
    """下发任务到设备。支持写字、提示词绘图、图片矢量化绘图。

    type=draw_generated 时 allow_dashscope 规则同 /dlc/tasks/preview。
    """
    # → dlc_core.handle_write / handle_draw / handle_draw_from_image → dlc_core.dispatch_task
    return {"task_id": "...", "status": "dispatched"}

@router.get("/dlc/tasks/{task_id}")
async def get_task(task_id: str, token: str = Depends(verify_dlc_api_token)):
    """查询任务状态。"""
    return {"task_id": task_id, "status": "completed", "result": {...}}

@router.get("/dlc/devices/{device_id}/status")
async def get_device_status(device_id: str, token: str = Depends(verify_dlc_api_token)):
    """查询设备实时状态。供小智云 dlc.get_device_status MCP tool 调用。"""
    # → registry.get(device_id) + active_tasks_for_device(device_id) + shadow_store.snapshot(device_id)
    return {
        "device_id": device_id,
        "online": True,
        "working": True,
        "active_task_id": "task-000001",
        "firmware_version": "u8-3.9.0",
        "last_seen_at": "...",
        "shadow": {...},
    }

@router.get("/dlc/knowledge")
async def get_plotter_knowledge(topic: str, query: str, token: str = Depends(verify_dlc_api_token)):
    """（可选）查询绘图机知识库。供 dlc.get_plotter_knowledge MCP tool 调用。

    瘦身阶段优先使用小智控制台角色 prompt 实现知识问答；
    仅当需要动态错误码/故障库时才启用此路由。
    """
    # → 读取 docs/xiaozhi-cloud/plotter-knowledge.json 或 device_memory 故障记忆
    return {"topic": topic, "query": query, "answer": "...", "source": "..."}
```

**`dlc_api` 鉴权矩阵**

| 端点 | 调用方 | 鉴权依赖 | device_id 校验 |
|------|--------|----------|----------------|
| `/health` | 运维/负载均衡 | 无 | 无 |
| `/dlc/tasks/preview` | 固件/MCP 内部 | `verify_dlc_api_token` | token 有效即可（仅生成/预览路径，不下发运动；配合 rate limit） |
| `/dlc/tasks/validate` | 固件 | `verify_dlc_api_token` | token 有效即可（仅做路径校验，不下发运动；配合 rate limit） |
| `/dlc/tasks/dispatch` | 固件/MCP 内部 | `verify_dlc_api_token` | `caller_device_id == body.device_id` |
| `/dlc/tasks/{task_id}` | 固件/MCP 内部 | `verify_dlc_api_token` | 校验 task 归属该 device_id |
| `/dlc/devices/{device_id}/status` | MCP 内部 | `verify_dlc_api_token` | `caller_device_id == path.device_id` |
| `/dlc/knowledge` | MCP 内部 | `verify_dlc_api_token` | token 有效即可（只读查询；配合 rate limit） |
| `/device/v1/app/devices/{id}/tasks` | 小程序 | `authorize(JWT)` + `require_device_control` | JWT 账户拥有/共享控制该设备 |
| `/device/v1/app/devices/{id}/status` | 小程序 | `authorize(JWT)` + `require_device_access` | JWT 账户拥有/共享查看该设备 |

说明：
- `verify_dlc_api_token` 生产环境优先查询数据库表 `v2_device_token`；`device_gateway/auth.configured_device_tokens()`（`LIMA_DEVICE_TOKENS`）仅作为开发/应急 fallback。
- 每台固件在激活/配网时由服务端下发独立的 per-device token，写入固件 NVS，避免全 fleet 共享单一 token（§13.1 S7）。
- 小程序路径保留现有 JWT + per-device 所有权校验，不改为共享 token。

### 3.4 dlc_mcp 工具定义

```python
# dlc_mcp/server.py
import json

from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("dlc-drawing")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="dlc.write_text",
            description="生成写字运动路径。输入文字，返回路径坐标和预览SVG。",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要写的文字（1-40字符）"},
                    "font_style": {"type": "string", "enum": ["default","handwriting","calligraphy"], "default": "default"},
                    "size": {"type": "string", "enum": ["small","medium","large"], "default": "medium"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="dlc.draw_generated",
            description="生成绘图运动路径。输入提示词，返回SVG路径和预览。支持预设图形（圆/方/三角/星/心）和手写字体路径。本 MCP 工具仅使用本地预设/字体生成路径，不调用 DashScope AI 生图。",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "绘图提示（1-80字符）"},
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="dlc.draw_from_image",
            description="从图片URL生成绘图运动路径。输入图库图片或用户上传图片的HTTPS URL，经矢量化后返回SVG路径和预览。",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "format": "uri", "description": "图片HTTPS URL（来自图库或用户上传）"},
                    "skeletonize": {"type": "boolean", "default": True, "description": "是否使用笔画细化模式（适合线稿/照片转笔画）"},
                },
                "required": ["image_url"],
            },
        ),
        Tool(
            name="dlc.validate_path",
            description="校验运动路径是否安全（坐标边界、点数限制、feed限制）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="dlc.get_device_status",
            description="查询绘图机实时状态：在线/离线、是否工作中、当前任务ID、固件版本、最后运动事件。",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "设备ID"},
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="dlc.get_plotter_knowledge",
            description="（可选）查询绘图机知识库：错误码含义、操作步骤、安全须知。当用户询问绘图机相关知识时调用。",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["error_code", "safety", "operation", "hardware"],
                        "description": "知识主题",
                    },
                    "query": {"type": "string", "description": "具体问题或错误码"},
                },
                "required": ["topic", "query"],
            },
        ),
        # dlc.dispatch_task 已从 MCP tool 列表移除
        # 理由：LLM 已有 dlc.write_text → 自行调 self.motor.run_path 的链式路径，
        #       以及 dlc.get_device_status 查询设备。暴露 dispatch_task 会引入
        #       LLM 选择复杂度（判断何时先调 write_text 再 dispatch vs 直接 dispatch），
        #       实际增加幻觉风险。dispatch 能力保留在 HTTP API（/dlc/tasks/dispatch）
        #       供小程序/外部调用，不对 LLM 暴露。
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "dlc.write_text":
        result = await dlc_core.handle_write(arguments["text"], ...)
    elif name == "dlc.draw_generated":
        # MCP tool 禁止使用 DashScope AI 生图，仅使用本地预设/字体
        result = await dlc_core.handle_draw(arguments["prompt"], allow_dashscope=False, ...)
    elif name == "dlc.draw_from_image":
        result = await dlc_core.handle_draw_from_image(
            arguments["image_url"],
            skeletonize=arguments.get("skeletonize", True),
        )
    elif name == "dlc.validate_path":
        result = dlc_core.validate_path(arguments["path"])
    elif name == "dlc.get_device_status":
        result = await dlc_core.get_device_status(arguments["device_id"])
    elif name == "dlc.get_plotter_knowledge":
        result = dlc_core.get_plotter_knowledge(arguments["topic"], arguments["query"])
    # dlc.dispatch_task 已从 MCP tool 移除，dispatch 仅通过 HTTP API 提供
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
```

#### `dlc.draw_generated` / `handle_draw` 调用方差异

| 调用方 | `allow_dashscope` | 行为 | 理由 |
|--------|-------------------|------|------|
| 小智云 MCP `dlc.draw_generated` | `False` | 仅用本地预设图形/字体生成路径 | 避免 LLM 语音路径依赖 DashScope 付费/延迟；MCP tool 超时 30s 内必须返回 |
| 固件 `self.plotter.draw_generated` | `False` | 同上 | 固件 tool 内部调 dlc_api，走相同安全策略 |
| 小程序 HTTP `/dlc/tasks/preview` `type=draw_generated` | 可 `True` | 允许调用 DashScope 文生图，再矢量化成路径 | 保留小程序 AI 绘图能力；用户明确在小程序点击“AI 绘图”，付费/延迟可接受 |
| 小程序 HTTP `/device/v1/app/devices/{id}/tasks` `capability=draw_generated` | 可 `True` | 同上 | 小程序任务下发入口 |

> **Ponytail 决策：** 同一函数 `dlc_core.handle_draw` 通过 `allow_dashscope` 参数区分调用方能力；MCP/固件路径强制 `False`，小程序路径可选 `True`。避免为两种场景写两套绘图函数。

### 3.5 路由注册变更

#### P2 后的 `server_dlc.py`

```python
# server_dlc.py — DLC 生产入口
from fastapi import FastAPI
from dlc_api.routes import router as dlc_router

app = FastAPI(title="DLC Drawing Service", version="1.0.0")
app.include_router(dlc_router)

if __name__ == "__main__":
    import uvicorn
    # S9：仅监听 127.0.0.1，公网流量必须经 nginx TLS 终止
    uvicorn.run(app, host="127.0.0.1", port=8080)
```

#### 被移除的路由（P2 从新入口中摘掉）

| 注册函数 | 路由 | 处理 |
|---------|------|------|
| `_register_chat_and_media_routes` | chat_endpoints, images, public_demo, embeddings | 不导入 |
| `_register_admin_and_static_routes` | admin, client_keys, static_files, upload, digital_human | 不导入 |
| `_register_voice_routes` | gemini_live_proxy, voice_pipeline_ws | 不导入 |
| `_register_optional_routes` | ops_metrics, health_dashboard, fleet, outcome_ingest, admin_probe_ingress, token_sync, device_memory, device_support | 不导入 |

#### 保留的路由（P2 后按瘦身程度保留）

| 路由 | 保留原因 | 瘦身幅度 |
|------|---------|---------|
| `routes/device_app_tasks.py` | 任务查询/管理 | 瘦身后保留 |
| `routes/device_app_gallery.py` | 图库上传/列表/删除/下载（用户上传图绘图必备） | 瘦身后保留 |
| `routes/handwriting.py` | 写字预览 | 瘦身后保留 |
| `routes/device_gateway.py` | 设备注册/心跳 | 瘦身后保留 |
| `routes/device_gateway_ws.py` | WS 任务下发 | 瘦身后保留 |
| `routes/device_ota*.py` | 先冻结 | P4 决策 |
| 设备智能安全 | `device_intelligence/safety.py`、`schemas.py` | profile_limit_error、DeviceProfile schema，path_validator / profiles 依赖 |
| 路由模型 | `device_gateway/model_routing.py`、`protocol_families.py` | P3 迁移时精简或并入 dlc_core；当前 path_validator.py 直接依赖二者 |
| 设备画像 | `device_gateway/device_profile/`（`models.py`、`registry.py`） | `profiles.py` 依赖 DeviceProfile，迁移时需保留或简化 |

#### 图库与图片矢量化保留说明

图库功能（用户上传图片或系统提供图片进行绘图）必须保留，涉及以下模块：

| 模块 | 职责 | 保留/迁移方式 |
|------|------|--------------|
| `routes/device_app_gallery.py` | `/device/v1/app/gallery*` 上传/列表/删除/下载 | 保留 |
| `device_gateway/gallery_store.py` | 图库元数据存储 | 保留 |
| `integrations/telegram_bot/client.py` | Telegram Bot 图库图片存储后端 | 保留（AGENTS.md 硬规则：Telegram 通知通道已退役，但图库存储后端不是通知通道） |
| `xiaozhi_drawing/svg_converter.py` | 图片 → SVG 路径矢量化 | 保留，`dlc_core/draw.py` 调用 |
| `xiaozhi_drawing/path_optimizer.py` | 路径优化 | 保留 |
| `device_gateway/image_fallback.py` | DashScope 生图失败时的多后端降级 | **不迁移到 dlc_core**；P4 随 `routes/images.py` 一起删除；图片矢量化不依赖此文件 |

#### 现有 `/device/v1/app/*` 端点到 `dlc_core` 的映射

> 小程序（以及未来可能的 Web/H5 管理端）继续复用现有 `/device/v1/app/*` 端点，**不改为 `/dlc/*`**。`dlc_api` 的 `/dlc/*` 仅面向固件 MCP 工具内部调用。本节明确现有设备端点如何落地到 `dlc_core`。

| 路由文件 | 端点 | 当前实现 | 瘦身后映射到 `dlc_core` | 备注 |
|----------|------|----------|------------------------|------|
| `routes/device_app_tasks.py` | `POST /devices/{device_id}/tasks` | `_build_app_gateway_task` → `validate_capability_params` → `project_to_motion_task_async` → `dispatch_or_enqueue` | 保留端点；内部改为调用 `dlc_core.intent_to_motion_task` → `dlc_core.dispatch_task`；`write_text`/`draw_generated`/`draw_from_image` 统一由 `dlc_core` 生成路径 | 小程序一键写字/画图/图库绘图的主入口 |
| `routes/device_app_tasks.py` | `GET /tasks?device_id=...` | 合并 `v2_task` 表 + `task_store.list_tasks_for_device` | 保留；查询来源不变，task store 仍用 Redis | |
| `routes/device_app_tasks.py` | `GET /tasks/{task_id}` | `task_snapshot` + `require_device_access` | 保留 | |
| `routes/device_app_api.py` | `GET /devices/{device_id}/status` | `_build_device_status`（registry + active_tasks_for_device） | 保留；内部聚合改为 `dlc_core.device_status.get_device_status`，复用同一来源 | 供小程序设备详情页 |
| `routes/device_app_status_ws.py` | `WS /devices/{device_id}/ws` | 轮询 `_build_device_status` 并推送 transition | 保留；调用 `routes/device_app_api._build_device_status`，后者再调 `dlc_core.device_status` | 小程序实时状态推送 |
| `routes/device_app_gallery.py` | `POST /gallery` / `GET /gallery` / `DELETE /gallery/{id}` / `GET /gallery/{id}/download` | Telegram 图库存储 + `gallery_store` | 保留；下载 URL 作为 `image_url` 供 `dlc_core.draw.handle_draw_from_image` 使用 | 用户上传/系统图片绘图必备 |
| `routes/device_app_provision.py` | `POST /devices/provision` / `POST /devices/provision/confirm` | `v2_pair_request` 表 + `bind_device` | **保留为唯一配网绑定端点**；P1 默认采用 pair_token 预绑定，经 SoftAP 写入设备 NVS（§5.2.6） | 一键配网账户绑定 |
| `routes/device_app_api.py` | `POST /devices/register` / `POST /devices/bind` / `GET /devices` / `GET/PUT /devices/{id}` / `POST /devices/{id}/unbind` | 现有 CRUD | 保留；绑定/解绑与绘图核心无关，但设备所有权校验是 `dlc_core.dispatch` 安全前提 | |
| `routes/device_app_api.py` | `GET /devices/{device_id}/tasks` | （若存在）统一合并到 `routes/device_app_tasks.py` | P3 去重：如有重复端点，归并到 `device_app_tasks.py` | 避免同功能多入口 |
| `routes/device_app_discovery.py` | 配网发现相关 | 与 `device_app_provision.py` 重复 | **P3 删除**；`device_app_provision.py` 成为唯一配网绑定端点 | |
| `routes/handwriting.py` | 写字预览相关 | 可能复用 `device_gateway` 逻辑 | P3 评估：若功能与 `/devices/{id}/tasks` 重复，则归档；否则改为调 `dlc_core.handle_write` | |

**调用链路示例（小程序一键写字）：**

```text
小程序 POST /device/v1/app/devices/{id}/tasks
  {capability: "write_text", params: {text: "你好"}}
  ↓
routes/device_app_tasks.py:create_task
  authorize(JWT) + require_device_control
  ↓
dlc_core.task_model.intent_to_motion_task({capability:"write_text", params:{text:"你好"}})
  ↓
dlc_core.write.handle_write("你好", device_id="...")
  → text_to_path → precheck_path → preview_svg
  ↓
dlc_core.dispatch.dispatch_task(device_id, task)
  → task_store 入队 → 设备 WS/MQTT 下发
  ↓
ESP32 U8 执行
```

**调用链路示例（小程序图库图片绘图）：**

```text
小程序 GET /device/v1/app/gallery/{id}/download
  → 返回 Telegram 临时 HTTPS URL
  ↓
小程序 POST /device/v1/app/devices/{id}/tasks
  {capability: "draw_from_image", params: {image_url: "https://api.telegram.org/..."}}
  ↓
dlc_core.draw.handle_draw_from_image(image_url, device_id="...")
  → 立即下载图片到 /tmp/dlc_uploads/ → svg_converter → precheck_path
  ↓
dlc_core.dispatch.dispatch_task(device_id, task)
  → 设备执行
```

> **Ponytail 决策：** 小程序端点路径和鉴权链**保持不变**，仅把内部路径生成逻辑替换为 `dlc_core`。这样小程序改造量最小，且保留现有 JWT + 设备所有权校验的安全防线。

### 3.6 删除清单（P4 物理删除）

#### 3.6.1 Chat/OpenAI compatible 子系统

```
routes/chat_endpoints.py
routes/chat_handler.py
routes/chat_handler_dispatch.py
routes/chat_preflight.py
routes/chat_stream.py
routes/chat_response_finalize.py
routes/chat_fallback.py
routes/chat_post_closeout.py
routes/chat_support.py
routes/v3_adapters.py
routes/images.py
routes/images_backends.py
routes/images_cache.py
routes/images_pollinations.py
routes/public_demo.py
routes/embeddings.py
routes/digital_human.py
```

#### 3.6.2 聊天路由引擎

```
routing_engine/
router_v3/
routing_selector/
routing_executor*
routing_classifier.py
routing_intent.py
```

#### 3.6.3 后端注册与探测

```
backends_registry/
backends_constants.py
provider_automation/
provider_inventory/
packages/provider-probe-offline/
probe_loop.py
backend_probe_loop.py
```

#### 3.6.4 聊天增强链路

```
context_pipeline/
session_memory/
code_context/
skill_store*
semantic_cache*
response_validator*
```

#### 3.6.5 Voice/Digital Human

```
device_voice/
data/digital-human/
routes/gemini_live_proxy.py
routes/voice_pipeline_ws.py
routes/device_app_voice.py
routes/ws_voiceprint_helpers.py
routes/ws_voice_transcript_helpers.py
routes/voice_pipeline_ws.py
routes/device_voice_ws_helpers.py
```

#### 3.6.6 Admin/Static

```
routes/admin*.py
routes/admin_ui/
routes/client_keys*.py
routes/static_files.py
routes/upload.py
```

#### 3.6.7 Optional Ops

```
routes/ops_metrics*
routes/health_dashboard.py
routes/fleet_api.py
routes/outcome_ingest.py
routes/admin_probe_ingress.py
routes/token_sync.py
routes/device_memory.py
routes/device_support.py
```

#### 3.6.8 Chat Web/官网/部署脚本

```
scripts/deploy_chat_web.py
scripts/deploy_site*.py
scripts/deploy_docs*.py
```

#### 3.6.9 对应测试文件

```
tests/test_routes_chat_*（9个）
tests/test_provider_*（13个）
tests/test_session_*（6个）
tests/test_context_pipeline_*
tests/test_routing_*
tests/test_skill_store*
tests/test_response_validator*
tests/test_routes_embeddings.py
tests/test_routes_public_demo.py
tests/test_routes_images*.py
tests/test_routes_health_dashboard.py
tests/test_routes_voice*.py
tests/test_device_voice_*.py
```

#### 3.6.10 依赖清理

```diff
# requirements_server.txt — 删除
- openai
- anthropic
- sentry-sdk
- prometheus-client

# 保留（瘦身后的 dlc_api 依赖）
  fastapi
  uvicorn
  httpx        # 设备通信 + 小程序 HTTP 路径调用 dlc_api 需要
  redis / sqlite
  opencv-python / numpy / pillow
  pydantic
  mcp>=1.6.0   # dlc_mcp 需要
  dashscope    # 必须保留：AI 生图能力（DashScopeImageClient）在 P1 不纳入 MCP tool，
               # 仅通过小程序 HTTP 路径（/dlc/tasks/preview type=draw_generated）保留

# requirements_voice.txt — 整个文件删除
```

---

## 4. 固件端改造（ESP32 U8）

### 4.1 当前固件 MCP 工具清单

U8 固件当前通过 `DlcMotorControlP1AiBoard::InitializeTools()` 注册以下 9 个 `self.motor.*` 工具：

| 工具名 | 参数 | 调用 |
|--------|------|------|
| `self.motor.home` | — | `executor_.ExecuteHomeCapability()` |
| `self.motor.get_status` | — | `ExecuteGetStatusCapability()` |
| `self.motor.get_device_info` | — | `ExecuteGetDeviceInfoCapability()` |
| `self.motor.pause` | — | `ExecutePauseCapability()` |
| `self.motor.resume` | — | `ExecuteResumeCapability()` |
| `self.motor.stop` | — | `ExecuteStopCapability()` |
| `self.motor.move_abs` | x,y,z,feed | `ExecuteMoveCapability(x,y,z,feed)` |
| `self.motor.move_rel` | dx,dy,dz,feed | `ExecuteMoveRelCapability(dx,dy,dz,feed)` |
| `self.motor.run_path` | path_json,feed | `RunPath(path_json,feed)` |

### 4.2 需要新增的 MCP 工具

当 DLC 服务端生成了路径后，需要设备端执行。当前 `self.motor.run_path` 已经可以接收 `path_json`，但需要增加两个高层工具让小智云 LLM 更容易调用：

| 新增工具名 | 参数 | 说明 | 调用链 |
|-----------|------|------|--------|
| `self.plotter.write_text` | text:string(1-40), feed:int(1-20000,default:1200) | 直接在设备端执行写字 | 先调用 dlc_api 生成 path → 再执行 run_path |
| `self.plotter.draw_generated` | prompt:string(1-80), feed:int(1-20000,default:1200) | 直接在设备端执行绘图 | 先调用 dlc_api 生成 path → 再执行 run_path |

**实现策略一（推荐）：设备端 tool 调用服务端 dlc_api**

> ✅ 固件已有稳定的 outbound HTTP/HTTPS 先例：
> - `u8-xiaozhi/main/ota.cc`：OTA 版本检查通过 `network->CreateHttp(0)` 发起 HTTPS POST。
> - `u8-xiaozhi/main/mcp_server.cc`：屏幕截图上传通过 `Board::GetInstance().GetNetwork()->CreateHttp(3)` 发起 multipart POST。
> - `u8-xiaozhi/main/assets.cc`、`boards/common/esp_video.cc`、`boards/common/esp32_camera.cc` 均使用同一抽象下载图片/视频。
>
> 因此 `self.plotter.write_text` / `self.plotter.draw_generated` 可直接复用 `Board::GetInstance().GetNetwork()->CreateHttp()`，无需引入新的 HTTP 客户端。
>
> 证据文件：
> - `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc:211`
> - `esp32S_XYZ/firmware/u8-xiaozhi/main/mcp_server.cc:209`
> - `esp32S_XYZ/firmware/u8-xiaozhi/main/assets.cc:436`

```cpp
// u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc
// 依赖：#include "nvs_flash.h" / "nvs.h"

// 从 NVS 读取 per-device token（安全审计 S7：禁止烧录进镜像的共享 token）
std::string DlcMotorControlP1AiBoard::GetDlcApiToken() {
    char token[128] = {0};
    size_t len = sizeof(token);
    nvs_handle_t handle;
    if (nvs_open("dlc", NVS_READONLY, &handle) == ESP_OK) {
        nvs_get_str(handle, "api_token", token, &len);
        nvs_close(handle);
    }
    return std::string(token);
}

// 帮助函数：发起 HTTPS POST 并返回响应字符串
std::string DlcMotorControlP1AiBoard::PostDlcApi(const std::string& path, const std::string& body) {
    // SEC-007：强制 HTTPS，防止 token 明文传输
    const std::string base_url = CONFIG_DLC_API_BASE_URL;
    if (base_url.rfind("https://", 0) != 0) {
        ESP_LOGE(TAG, "DLC_API_BASE_URL must be https://");
        return "";
    }

    const std::string token = GetDlcApiToken();
    if (token.empty()) {
        ESP_LOGE(TAG, "dlc api_token not found in NVS");
        return "";
    }

    auto http = Board::GetInstance().GetNetwork()->CreateHttp(0);
    http->SetHeader("Content-Type", "application/json");
    http->SetHeader("Accept", "application/json");
    http->SetHeader("Authorization", "Bearer " + token);
    http->SetContent(body);
    // 建议设置 10s 超时，避免 MCP tool_call_timeout 内无法返回
    // http->SetTimeout(10000);  // 若 Board Network 抽象支持

    std::string url = base_url + path;
    if (!http->Open("POST", url)) {
        return "";
    }

    int status = http->GetStatusCode();

    // SEC-005：不能先 ReadAll 再判大小；必须分块读取并在超限时中断
    constexpr size_t kMaxResponseBytes = 128 * 1024;
    std::string response;
    response.reserve(4096);
    while (true) {
        std::string chunk = http->ReadSome();  // 若抽象层无 ReadSome，则需改造 Network/Http 接口
        if (chunk.empty()) {
            break;
        }
        response.append(chunk);
        if (response.size() > kMaxResponseBytes) {
            ESP_LOGE(TAG, "dlc_api response too large: %zu", response.size());
            http->Close();
            return "";
        }
    }
    http->Close();
    return (status == 200) ? response : "";
}

// 辅助：安全解析 JSON；SEC-004：ESP-IDF 默认禁用 C++ 异常，parse 失败会 abort
static nlohmann::json SafeParseJson(const std::string& text) {
    return nlohmann::json::parse(text, nullptr, false);
}

// 写字：设备端先调 dlc_api 生成路径，再本地执行
mcp_server.AddTool("self.plotter.write_text", "在绘图机上写字",
    PropertyList({
        Property("text", kPropertyTypeString, "", "要写的文字（1-40字符）"),
        Property("feed", kPropertyTypeInteger, 1200, 1, 20000, "进给速度")
    }),
    [this](const PropertyList& props) -> ReturnValue {
        std::string text = props["text"].value<std::string>();
        int feed = props["feed"].value<int>();

        // 1. 调用 dlc_api 生成路径
        std::string request_body = nlohmann::json{
            {"type", "write_text"},
            {"text", text}
        }.dump();
        std::string preview_response = PostDlcApi("/dlc/tasks/preview", request_body);
        if (preview_response.empty()) {
            return "路径生成失败：dlc_api 无响应";
        }
        auto preview_json = SafeParseJson(preview_response);
        if (preview_json.is_discarded() || !preview_json.contains("path")) {
            return "路径生成失败：dlc_api 返回异常";
        }

        // 2. 安全校验（可选，dlc_api 已在服务端校验；固件端做二次校验更保险）
        std::string path_body = nlohmann::json{{"path", preview_json["path"]}}.dump();
        std::string validate_response = PostDlcApi("/dlc/tasks/validate", path_body);
        if (!validate_response.empty()) {
            auto validate_json = SafeParseJson(validate_response);
            if (!validate_json.is_discarded() && validate_json.contains("ok")
                && !validate_json.value("ok", false)) {
                return "路径校验失败: " + validate_json.value("errors", "unknown").dump();
            }
        }

        // 3. 本地执行路径
        std::string taskId = protocol_.NextLocalTaskId("mcp_write");
        return executor_.RunPath(taskId, preview_json["path"].dump(), feed);
    });

// 绘图：设备端先调 dlc_api 生成路径，再本地执行
mcp_server.AddTool("self.plotter.draw_generated", "在绘图机上画图",
    PropertyList({
        Property("prompt", kPropertyTypeString, "", "绘图提示（1-80字符）"),
        Property("feed", kPropertyTypeInteger, 1200, 1, 20000, "进给速度")
    }),
    [this](const PropertyList& props) -> ReturnValue {
        std::string prompt = props["prompt"].value<std::string>();
        int feed = props["feed"].value<int>();

        std::string request_body = nlohmann::json{
            {"type", "draw_generated"},
            {"prompt", prompt}
        }.dump();
        std::string preview_response = PostDlcApi("/dlc/tasks/preview", request_body);
        if (preview_response.empty()) {
            return "绘图生成失败：dlc_api 无响应";
        }
        auto preview_json = SafeParseJson(preview_response);
        if (preview_json.is_discarded() || !preview_json.contains("path")) {
            return "绘图生成失败：dlc_api 返回异常";
        }

        std::string taskId = protocol_.NextLocalTaskId("mcp_draw");
        return executor_.RunPath(taskId, preview_json["path"].dump(), feed);
    });
```

**实现策略二（备选）：服务端 tool 返回 path 后由小智云调 self.motor.run_path**

小智云 LLM 先调 `dlc.write_text` 拿到 `{path: [...]}`，服务器将结果以 `role="tool"` 写回对话历史后，再次调用 LLM；LLM 在下一轮决策中调用 `self.motor.run_path(path_json=...)`。

- `dlc.write_text` 返回 `{path: [...]}`
- 小智云 LLM 调用 `self.motor.run_path(path_json=dlc.write_text.path)`

U8 的 `HandleMotionTaskJson` 已兼容 `path_json` 字符串和 `path` 数组两种入参
（见 `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc`）。

**代码证据：** 官方仓库 `xinnan-tech/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py` 中：
- `MAX_DEPTH = 5` 允许最多 5 层工具调用递归；
- `_handle_function_result()` 对 `Action.REQLLM` 的结果写入 `role="tool"`；
- 然后调用 `self.chat(None, depth=depth + 1)` 让 LLM 基于工具结果继续决策。

这意味着**自托管服务器架构已原生支持**服务端 tool → 设备端 tool 的链式调用；官方云大概率复用同一机制，但 P0 仍需用真实 `xiaozhi.me` 账号实测确认（无法直接读取闭源官方云代码）。

若实测不通过，则默认采用实现策略一（固件端 tool 直接调 dlc_api，对 LLM 只需一次 tool call）。

### 4.3 固件需要修改的文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc` | 按 4.2 新增 2 个 AddTool + `PostDlcApi` 帮助函数 | 注册 `self.plotter.write_text` / `self.plotter.draw_generated` |
| `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/motion_executor.h` | 新增 `std::atomic<bool> motion_busy_{false}` 私有成员 | **防呆机制**：运动忙标志，见 §1.6.6 |
| `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/motion_executor.cc` | `RunPathWithTaskId` / `ExecuteHomeWithTaskId` / `ExecuteMoveWithTaskId` / `ExecuteMoveRelWithTaskId` 入口添加 `motion_busy_.compare_exchange_strong` + RAII guard | **防呆机制**：拒绝运动中再次接受新运动任务；`pause`/`resume`/`stop` 不加锁 |
| `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc` | 新增 `GetDlcApiToken()` 私有方法 | 从 NVS namespace `dlc` key `api_token` 读取 per-device token（安全审计 S7） |
| `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/config.h` | 新增 `DLC_API_BASE_URL` 宏 | `#define DLC_API_BASE_URL "https://chat.donglicao.com"`；**token 不通过 Kconfig 硬编码** |
| `u8-xiaozhi/main/Kconfig.projbuild` | 新增 `CONFIG_DLC_API_BASE_URL` 配置项 | 允许编译时配置 dlc_api 地址；**token 通过激活/配网流程写入 NVS** |
| `u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.h` | 无新增持久成员 | HTTP 通过 `Board::GetInstance().GetNetwork()->CreateHttp()` 临时创建 |
| `u8-xiaozhi/main/mcp_server.cc` | 无改动 | 通用工具不变 |
| `u8-xiaozhi/main/provisioning_contract.h` | 统一命名前缀：`kSoftApSsidPrefix` 从 `"Xiaozhi"` 改为 `"DLC"`；`kBlufiDeviceName` 从 `"Xiaozhi-Blufi"` 改为 `"DLC-Blufi"` | 与小程序端 `DLC-XXXXXX` / `DLC-Blufi` 对齐，解决当前配网名不一致导致搜不到设备的问题 |
| `u8-xiaozhi/main/boards/common/wifi_board.cc` | 无直接代码改动（已读取 `ProvisioningContract::kSoftApSsidPrefix`）| SoftAP SSID 由 `78/esp-wifi-connect` 组件生成：`{ssid_prefix}-{mac[4]:02X}{mac[5]:02X}`，AP 为 `WIFI_AUTH_OPEN`（[源码证据](https://github.com/78/esp-wifi-connect)）；修改前缀后自动得到 `DLC-AABB` |
| `u8-xiaozhi/main/boards/common/wifi_board.cc` | **可选：新增 SoftAP `/device-info` HTTP 端点** | 若采用“pair_token 预绑定”方案，需通过 SoftAP 暴露 `device_sn`/`mac`/`firmware_ver`；实现方式：fork `78/esp-wifi-connect` 在 `wifi_configuration_ap.cc` 注册新 URI，或在固件内并发动自定义 HTTP server（推荐前者，避免双 HTTP server 端口冲突） |
| `u8-xiaozhi/main/application.cc` | 新增 pair_token 绑定回调 | 连网后读取 NVS `wifi:pair_token`，调用 `POST /device/v1/app/devices/provision/confirm`，把响应中的 `dlcApiToken` 写入 NVS namespace `dlc` key `api_token`，再执行原有 `Ota::CheckVersion`（§5.2.6） |

**配网相关依赖与证据链：**

| 证据 | 来源 | 结论 |
|------|------|------|
| `78/esp-wifi-connect` SoftAP SSID 生成规则：`snprintf(ssid, sizeof(ssid), "%s-%02X%02X", ssid_prefix_.c_str(), mac[4], mac[5])` | [GitHub 源码](https://github.com/78/esp-wifi-connect) | 修改 `ssid_prefix` 即可得到 `DLC-XXXXXX` |
| SoftAP 认证模式：`wifi_config.ap.authmode = WIFI_AUTH_OPEN` | [GitHub 源码](https://github.com/78/esp-wifi-connect) | 无密码热点，`wx.connectWifi` 传 `password: ''` 即可连接 |
| `/submit` 只解析 `ssid` / `password` | [GitHub 源码](https://github.com/78/esp-wifi-connect) | 当前组件**不支持**直接透传 `server_host` / `device_secret` / `pair_token`；若设计需要，必须 fork 组件扩展 |
| `/exit` 端点存在 | [GitHub 源码](https://github.com/78/esp-wifi-connect) | 小程序可在 `/submit` 成功后调用 `/exit` 让设备关闭 SoftAP |
| `wx.connectWifi` 参数与限制 | [微信官方文档](https://developers.weixin.qq.com/miniprogram/dev/api/device/wifi/wx.connectWifi.html) | Android 10+ 需 `maunal: true` 才能让连接系统生效；iOS 需监听 `onWifiConnected` 事件验证；open 网络传空密码 |

### 4.4 固件 OTA 与配置

- 固件版本号在 `CMakeLists.txt` 或 `idf_component.yml` 中管理
- OTA 升级路径：`self.upgrade_firmware` 已存在，无需新增
- 配置：`DLC_API_BASE_URL` 通过 `menuconfig` 或 `sdkconfig.defaults` 配置；**`DLC_API_TOKEN` 不编译进镜像**，由激活/配网流程写入 NVS namespace `dlc` key `api_token`
- 配网方式：当前 `sdkconfig.defaults` 同时启用 `CONFIG_USE_ESP_BLUFI_WIFI_PROVISIONING=y` 和 `CONFIG_USE_HOTSPOT_WIFI_PROVISIONING=y`；一键配网方案以 SoftAP 为主路径，P2 后可评估关闭 BluFi 以节省固件体积
- `sdkconfig.defaults` 追加/调整：
  ```
  CONFIG_DLC_API_BASE_URL="https://chat.donglicao.com"
  # CONFIG_DLC_API_TOKEN 不再使用；per-device token 通过 NVS 写入
  # 如需使用 fork 的 esp-wifi-connect，修改 main/idf_component.yml 中依赖为自定义 git URL
  ```

### 4.5 固件测试

#### 功能测试

- 新增 native 单测：验证 `self.plotter.write_text` 和 `self.plotter.draw_generated` 的 MCP 工具注册
- 假 dlc_api 测试：mock HTTP 响应，验证 tool 回调逻辑
- **防呆测试**：在 `RunPathWithTaskId` 执行中并发调用第二个 `RunPath`，验证返回 `"device is busy"` 而不执行
- **防呆测试**：在 `RunPathWithTaskId` 执行中调用 `ExecutePauseCapability`，验证 pause 仍可执行（不受 busy 锁限制）
- **配网测试**：验证 SoftAP SSID 前缀为 `DLC`；验证 `/scan` 返回格式；验证 `/submit` 携带 ssid/password 时设备保存凭据

#### 安全审计验收测试（对应 §13）

| 测试项 | 对应审计编号 | 验收标准 |
|--------|-------------|---------|
| Token 不烧录镜像 | S7 | 固件镜像中不存在 `CONFIG_DLC_API_TOKEN` 字符串；`GetDlcApiToken()` 从 NVS 读取且为空时拒绝调用 dlc_api |
| HTTPS 强制 | SEC-007 | `CONFIG_DLC_API_BASE_URL="http://..."` 时 `PostDlcApi` 返回空字符串并记录错误日志 |
| TLS 证书校验 | SEC-006 | 单元测试确认 `CreateHttp()` 启用证书校验；抓包验证不会跳过服务端证书验证 |
| 响应体大小限制 | SEC-005 | Mock dlc_api 返回 129KB 响应，`PostDlcApi` 返回空字符串且不发生 OOM |
| JSON 异常保护 | SEC-004 | Mock dlc_api 返回非 JSON 或畸形 JSON，`self.plotter.write_text` 返回错误字符串，设备不崩溃/不重启 |
| Path 段数/长度上限 | SEC-001/002/003 | 构造 `path_json` 含 201 段或 33KB，`RunPathWithTaskId` 返回 `"path exceeds max segments"` / `"path json too large"`；构造 200 段/32KB 正常执行 |
| 相对移动范围 | 现有 | `dx/dy/dz` 超出 `[-1, 1]` 返回错误，不执行 |
| Feed 范围 | 现有 | `feed` 不在 `[1, 20000]` 返回错误 |
| 坐标边界 | 现有 | `x/y/z` 超出 `±500mm` 或含 `NaN/Inf` 返回错误 |
| pair_token 绑定 | §5.2.6 | Mock `/devices/provision/confirm` 返回 `dlcApiToken`，验证设备将其写入 NVS `dlc:api_token`，后续 `PostDlcApi` 使用该 token |

#### CI

- 在 `esp32S_XYZ/.github/workflows/` 中新增 `firmware-dlc-tools` job，覆盖上述功能 + 安全验收测试

---

## 5. 小程序端改造

### 5.1 当前小程序架构

- 微信小程序，uni-app + Vue3 + TypeScript
- 版本：3.8.7（versionCode: 387）
- API 前缀：`/device/v1/app`
- 服务端：`https://chat.donglicao.com`
- 构建命令：`npx uni build --platform mp-weixin`
- 上传：微信开发者工具 CLI

### 5.2 需要修改的内容

#### 5.2.1 API 前缀变更

当 LiMa 瘦身后，小程序的 API 前缀需要适配新服务端：

```typescript
// src/api/v2/index.ts
// 瘦身前
const appPrefix = '/device/v1/app'

// 瘦身后（方案1：保持兼容）
const appPrefix = '/device/v1/app'  // dlc_api 保持旧前缀

// 瘦身后（方案2：新前缀）
const appPrefix = '/dlc/v1'  // dlc_api 新前缀
```

**推荐方案 1**：`dlc_api` 保持 `/device/v1/app` 前缀，小程序端 API 路径不变，避免大量改动。

#### 5.2.2 需要修改的文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/api/v2/index.ts` | 无改动（方案 1） | 保持 `/device/v1/app` 前缀 |
| `src/utils/index.ts` | 简化 `getChatBaseUrl` | 删除 `aliyun.donglicao.com` 分流逻辑 |
| `src/api/chat/chat.ts` | 删除或标注 deprecated | 普通对话走小智云，不走 LiMa |
| `src/api/chat-history/chat.ts` | 删除或标注 deprecated | 对话历史走小智云 |
| `src/api/images/images.ts` | 改指 dlc_api | AI 图像生成保留，统一调用 `/dlc/tasks/preview` `type=draw_generated`（DashScope） |
| `src/api/gallery/gallery.ts` | 保留 | 图库上传/列表/删除/下载 API 不变 |
| `src/hooks/useUpload.ts` | 保留 | 图库/本地上传通用 hook |
| `src/utils/uploadFile.ts` | 保留 | 文件上传到图库 |
| `src/pages/create/components/image-picker.vue` | 保留 + 扩展 | 图片选择器：支持本地上传 + 图库选择，选图后调 `v2SubmitTask(deviceId, 'draw_from_image', {image_url})` |
| `src/pages/chat/chat.vue` | 标注 deprecated | 对话页面不再需要（走小智设备） |
| `src/pages/chat-history/` | 删除 | 不再需要 |
| `src/pages/create/ai-draw.vue` | 简化 | 直接调 `v2SubmitTask(deviceId, 'draw_generated', {prompt})` |
| `src/pages/create/image-draw.vue` | 简化 | 直接调 `v2SubmitTask` |
| `src/pages/v2/device-detail/components/write-draw-panel.vue` | 无改动 | 已有 write/draw UI |
| `src/pages/index/index.vue` | 删除 chat/digital-human 入口 | 只保留 draw/write |
| `src/pages/index/composables/useHomeNavigation.ts` | 删除 goChat/goDigitalHuman 定义+返回 | |
| `src/pages/index/composables/useHomeData.ts` | 删除 chat 相关数据 | |
| `src/pages/device-config/index.vue` | 简化为一键 SoftAP 配网 | 删除方式选择，默认 SoftAP + 自动连热点（§5.2.6） |
| `src/pages/device-config/components/wifi-config.vue` | 自动化热点检测+wx.connectWifi | 自动连 DLC-XXXXXX 热点；连上后自动调 /scan |
| `src/pages/device-config/components/blufi-config.vue` | 标注 deprecated | P2 冻结，P4 删除 |
| `src/pages/device-config/components/ultrasonic-config.vue` | 删除 | 已注释禁用 |
| `src/pages/device-config/provisioning-contract.ts` | 修正 SSID 前缀 | `softApSsidHint` 与固件统一为 `DLC-XXXXXX` |
| `src/api/v2/index.ts` | 新增 pair-status 查询 | `GET /device/v1/app/devices/pair-status` |
| `manifest.config.ts` | versionName 3.8.7 → 3.9.0 | major 改动 |
| `src/pages.json` | 移除 chat/chat-history 的 3 条 page 注册项 | 否则 uni build 报错 |

#### 5.2.3 需要删除的页面/组件

| 删除项 | 理由 |
|--------|------|
| `src/pages/chat/` | 对话走小智云，不走 LiMa |
| `src/pages/chat-history/` | 对话历史走小智云 |
| `src/api/chat/` | 不再需要 |
| `src/api/chat-history/` | 不再需要 |
| `src/pages/index/index.vue` 中的 `goChat` / `goDigitalHuman` | 不再需要 |

#### 5.2.4 需要保留的页面/组件

| 保留项 | 理由 |
|--------|------|
| `src/pages/v2/device-list/` | 设备列表主页 |
| `src/pages/v2/device-detail/` | 设备详情 + write-draw-panel |
| `src/pages/create/ai-draw.vue` | AI 绘图 |
| `src/pages/create/image-draw.vue` | 图片绘图 |
| `src/pages/device-config/` | 设备配网 |
| `src/pages/settings/` | 设置 |
| `src/pages/voiceprint/` | 声纹（小智云相关） |
| `src/api/v2/` | 设备 v2 API（任务下发、状态查询） |
| `src/pages/v2/device-detail/components/write-draw-panel.vue` | 写画面板 |

#### 5.2.5 版本号变更

```typescript
// manifest.config.ts
'versionName': '3.9.0',  // 3.8.7 → 3.9.0（Slimdown major change）
'versionCode': 390,      // 387 → 390
```

#### 5.2.6 一键配网改造

**现状问题：**

当前配网流程步骤多、操作复杂，用户容易卡住：

| 路径 | 步骤 | 痛点 |
|------|------|------|
| BluFi（BLE，默认） | 5 步：选方式→手输 SSID/密码→扫描 BLE→选设备连接→下发 | 需手输 WiFi 名+密码；需手动选蓝牙设备；BLE 连接不稳定时用户不知道怎么办 |
| SoftAP HTTP | 4 步：手机连热点→选 WiFi→输密码→点开始 | 需手动切手机 WiFi 到设备热点；用户不理解"连热点"概念 |

**其他不足：**
- 固件设备名 `Xiaozhi-Blufi` / SoftAP SSID `Xiaozhi` 前缀与小程序端 `DLC-Blufi` / `DLC-XXXXXX` **不一致**，配不通
- 小程序 BluFi 载荷用 JSON UTF-8 直写（非 ESP BluFi 标准帧），需对接改造固件
- `device_app_provision.py` 与 `device_app_discovery.py` 两套重复的 pair/provision 端点

**一键配网目标：** 用户只需 2 步——**选 WiFi + 输密码 + 点"开始配网"**，其余全自动化。

**方案：SoftAP 为主路径 + 自动化引导**

选择 SoftAP 而非 BluFi 作为主路径的理由（Ponytail 最简方案）：
- SoftAP 不需要蓝牙权限（微信小程序蓝牙权限申请受限）
- SoftAP 步骤更少（4 步 → 简化到 2 步）
- **小程序蓝牙不适合传大数据流**：`wx.writeBLECharacteristicValue` 官方建议单次写入不超过 20 字节（蓝牙 4.0 限制），并行写还可能失败；未来若需 OTA 或传较长配置，SoftAP HTTP 明显更可控（[微信官方文档](https://developers.weixin.qq.com/miniprogram/dev/api/device/bluetooth-ble/wx.writeBLECharacteristicValue.html)）
- 固件已有稳定 SoftAP 实现（`wifi_board.cc:173-183`）
- BluFi 当前使用非标准帧，整改成本高

**简化后的用户流程（2 步）：**

```text
步骤 1：小程序检测到"未绑定设备" → 自动弹出配网引导
  ↓
步骤 2：用户看到动画引导（"请按设备 BOOT 键"）
  ↓ 用户按 BOOT 键 → 设备进入 SoftAP 模式
  ↓
步骤 3：小程序自动检测手机是否已连上 DLC-XXXXXX 热点
  ↓ 未连接 → 调 wx.connectWifi 自动连热点（open 网络，password 传空）
  ↓ 已连接 → 自动调 /scan 获取 WiFi 列表
  ↓
步骤 4：用户选 WiFi + 输密码 → 点"一键配网"
  ↓ 小程序自动调 /submit（仅携带 ssid+password）→ /exit
  ↓
步骤 5：设备连上 WiFi → 自动激活 → 小程序显示"配网成功 ✓"
```

**用户实际操作只有 2-3 次**：按 BOOT 键 → 选 WiFi → 输密码 → 点一个按钮。

> **关键限制（来自 `78/esp-wifi-connect` 源码）：** 当前组件的 `/submit` 端点**只解析 `ssid` 与 `password`**，不会透传 `server_host` / `device_secret` / `pair_token`。若要把 pair_token 下发到设备，必须 fork 该组件扩展 `/submit` 解析逻辑，并新增 `/device-info` 端点暴露 `device_sn`/`mac`。**本方案默认采用 pair_token 预绑定路径**，P1 必须 fork 组件完成上述扩展；只有在无法及时 fork 时才回退到无 pair_token 透传的最小改动方案。

**小程序改造清单：**

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/pages/device-config/index.vue` | 简化为单一 SoftAP 路径 | 删除 BluFi/SoftAP 方式选择；默认 SoftAP；加入动画引导 |
| `src/pages/device-config/components/wifi-config.vue` | 自动化热点检测+连接 | 调 `wx.connectWifi` 自动连 DLC-XXXXXX；连上后自动调 `/scan`；失败时 fallback 到手动连热点 |
| `src/pages/device-config/components/wifi-selector.vue` | 保持 | 选 WiFi + 输密码 UI 不变；已兼容 `{aps:[...]}` 与 `{success,networks:[...]}` 两种返回格式 |
| `src/pages/device-config/components/blufi-config.vue` | 标注 deprecated | P2 冻结，P4 删除 |
| `src/pages/device-config/components/ultrasonic-config.vue` | 删除 | 已注释禁用 |
| `src/pages/device-config/provisioning-contract.ts` | 修正 SoftAP SSID 前缀说明 | `softApSsidHint` 保持 `DLC-XXXXXX`；固件侧改为 `DLC` 前缀后自然一致 |
| `src/api/v2/index.ts` | 新增 `GET /device/v1/app/devices/pair-status?deviceSn=...` | 轮询设备是否已上线并激活 |

**固件改造清单（统一命名 + 一键激活）：**

| 文件 | 改动 | 说明 |
|------|------|------|
| `provisioning_contract.h` | SoftAP SSID 前缀从 `Xiaozhi` 改为 `DLC` | 与小程序端 `DLC-XXXXXX` 统一 |
| `provisioning_contract.h` | BluFi 设备名从 `Xiaozhi-Blufi` 改为 `DLC-Blufi` | 统一命名（备用路径） |
| `78/esp-wifi-connect` 组件 | fork 后扩展 `/submit` | 解析 `pair_token` 字段并写入 NVS namespace `wifi` key `pair_token`；新增 `/device-info` 端点暴露 `device_sn`/`mac`/`firmware_ver` |
| `wifi_board.cc` | 无直接代码改动 | SoftAP SSID 由 fork 后的 `78/esp-wifi-connect` 组件生成；`/device-info` 端点在组件内实现，避免固件内双 HTTP server |
| `application.cc` | 新增 pair_token 绑定回调 | 连网后读取 NVS `wifi:pair_token`，调用 `POST /device/v1/app/devices/provision/confirm`，把响应中的 `dlcApiToken` 写入 NVS namespace `dlc` key `api_token`，再执行 `Ota::CheckVersion` |

**服务端改造（去重 + pair-status 查询）：**

| 文件 | 改动 | 说明 |
|------|------|------|
| `device_app_discovery.py` | 标注 deprecated | 与 `device_app_provision.py` 功能重复，P3 删除 |
| `device_app_provision.py` | 保留为唯一配网端点 | 扩展 `POST /devices/provision/confirm` 响应，返回 `dlcApiToken`（per-device token）；`POST /devices/provision` 保持现有逻辑不变 |
| `device_app_api.py` | 新增 `GET /device/v1/app/devices/pair-status?deviceSn=...` | 小程序轮询：设备是否已上线并绑定账户 |

**推荐方案：pair_token 预绑定（对接现有 `routes/device_app_provision.py`）**

> 服务端已有完整 pair_token 实现（`routes/device_app_provision.py:81-136`）：
> - `POST /device/v1/app/devices/provision` 创建 `provision_token`，写入 `v2_pair_request` 表并绑定到 `account_id + device_sn`，30 分钟有效。
> - `POST /device/v1/app/devices/provision/confirm` 校验 token 后调用 `bind_device()`，完成设备与账户的绑定。
>
> 本方案把 pair_token 经 SoftAP 写入设备 NVS，设备连网后主动调用 `/provision/confirm` 完成绑定，并**在响应中获取 per-device `dlc_api_token`**，写入 NVS namespace `dlc` key `api_token`。这同时解决了 §13.1 S7（固件共享 token）的安全问题。

```text
用户按 BOOT 键
  ↓
ESP32 → 进入 SoftAP 模式（AP: DLC-XXXXXX，open 网络）
  ↓
小程序 → wx.connectWifi({SSID:"DLC-XXXXXX", password:"", maunal:false})
         失败（Android 10+）→ 引导用户手动连接 或 maunal:true 跳转系统 WiFi
  ↓
小程序 → GET http://192.168.4.1/device-info  ← 取 device_sn / mac
  ↓
小程序 → POST /device/v1/app/devices/provision
         {deviceSn, wifiSsid, wifiPassword} ← 创建 pair_token，绑定 account + device_sn
  ↓
小程序 → POST http://192.168.4.1/submit
         {ssid, password, pair_token}  ← 扩展后下发 WiFi 凭据 + pair_token
  ↓
小程序 → POST http://192.168.4.1/exit    ← 关闭 SoftAP
  ↓
ESP32 → 连 WiFi → kDeviceStateActivating
  ↓
ESP32 → POST /device/v1/app/devices/provision/confirm
         {provisionToken: pair_token, deviceSn}
       ← 响应 {status:"bound", accountId, dlcApiToken}
  ↓
ESP32 → 把 dlc_api_token 写入 NVS namespace "dlc" key "api_token"
  ↓
ESP32 → Ota::CheckVersion()
  ↓
小程序 → 轮询 GET /device/v1/app/devices/pair-status?deviceSn=<deviceSn>
         返回 {activated: true, bound: true} → 显示"配网成功 ✓"
```

**固件激活回调改造（对接 pair_token）：**

```cpp
// u8-xiaozhi/main/application.cc — 在 ActivationTask / 连网后回调中新增
#include "nvs_flash.h"
#include "nvs.h"

static std::string ReadNvsString(const char* ns, const char* key) {
    char buf[256] = {0};
    size_t len = sizeof(buf);
    nvs_handle_t handle;
    if (nvs_open(ns, NVS_READONLY, &handle) == ESP_OK) {
        nvs_get_str(handle, key, buf, &len);
        nvs_close(handle);
    }
    return std::string(buf);
}

void OnNetworkConnectedAndReady() {
    // 1. 尝试用 pair_token 完成绑定
    std::string pair_token = ReadNvsString("wifi", "pair_token");
    std::string device_sn = GetDeviceSn();  // 已有函数
    if (!pair_token.empty()) {
        auto http = Board::GetInstance().GetNetwork()->CreateHttp(0);
        http->SetHeader("Content-Type", "application/json");
        std::string body = nlohmann::json{
            {"provisionToken", pair_token},
            {"deviceSn", device_sn}
        }.dump();
        http->SetContent(body);
        if (http->Open("POST", CONFIG_DLC_API_BASE_URL "/device/v1/app/devices/provision/confirm")) {
            int status = http->GetStatusCode();
            std::string resp = http->ReadAll();
            http->Close();
            if (status == 200) {
                auto json = nlohmann::json::parse(resp, nullptr, false);
                if (!json.is_discarded() && json.contains("dlcApiToken")) {
                    std::string api_token = json["dlcApiToken"].get<std::string>();
                    // 写入 NVS namespace "dlc" key "api_token"
                    nvs_handle_t dlc_handle;
                    if (nvs_open("dlc", NVS_READWRITE, &dlc_handle) == ESP_OK) {
                        nvs_set_str(dlc_handle, "api_token", api_token.c_str());
                        nvs_commit(dlc_handle);
                        nvs_close(dlc_handle);
                    }
                }
            }
        }
        // 绑定完成后可清空 pair_token（可选）
    }

    // 2. 继续原有 OTA/激活流程
    Ota::CheckVersion();
}
```

**服务端 `/provision/confirm` 响应扩展：**

```python
# routes/device_app_provision.py:_build_confirm_response 或 confirm_provision 返回体
{
    "deviceSn": device_sn,
    "status": "bound",
    "accountId": account_id,
    "dlcApiToken": dlc_api_token  # 新增：per-device token，供固件写入 NVS
}
```

`dlc_api_token` 生成方式：首次 confirm 时若该设备尚无 token，则生成 `secrets.token_urlsafe(32)`，计算 `sha256(token)` 后写入数据库表 `v2_device_token(device_id, token_hash, created_at, rotated_at)`；明文 token 仅在这一次 confirm 响应中返回给固件写入 NVS。`device_gateway/auth.configured_device_tokens()` 仅保留为开发/应急 fallback，不再作为生产 token 主存储。

**扩展 `/submit` 以透传 pair_token（必须 fork `78/esp-wifi-connect`）：**

```cpp
// 在 wifi_configuration_ap.cc 的 /submit handler 中新增
std::string pair_token;
if (cJSON_HasObjectItem(root, "pair_token")) {
    pair_token = cJSON_GetStringValue(cJSON_GetObjectItem(root, "pair_token"));
    nvs_handle_t handle;
    if (nvs_open("wifi", NVS_READWRITE, &handle) == ESP_OK) {
        nvs_set_str(handle, "pair_token", pair_token.c_str());
        nvs_commit(handle);
        nvs_close(handle);
    }
}
```

> **Ponytail 决策：** 推荐 pair_token 预绑定作为默认方案。它复用服务端已有实现、解决 per-device token 安全问题，且用户感知与最小改动方案一致。唯一额外工作是 fork `78/esp-wifi-connect` 扩展 `/submit`，这是 P1 必须完成的固件改动。

**Fallback 方案：最小改动（无 pair_token 透传）**

若 P1 无法及时 fork `78/esp-wifi-connect`，可回退到最小改动方案：
- `/submit` 仅下发 `{ssid, password}`；
- 设备连网后走原有 `Ota::CheckVersion() / Activate()`；
- 账户绑定走原有激活码或 `wx.getConnectedWifi` BSSID + 服务端轮询匹配；
- per-device `dlc_api_token` 通过首次成功连接后的 WS hello 交互或后续 OTA 下发。

此方案安全性较弱（token 需要后续通道下发），仅作为临时 fallback。


**用户感知体验：**

1. 小程序首页没有设备时自动弹出"添加设备"引导
2. 动画提示"按住设备 BOOT 键 2 秒"→ 设备进入配网
3. 小程序自动连接设备热点（用户无需手动切 WiFi）
4. 弹出 WiFi 列表→选 WiFi→输密码→点"一键配网"
5. 等待 10-20 秒→显示"配网成功"

> **Ponytail 决策：** 优先用微信 SDK `wx.connectWifi` 自动连接 SoftAP 热点，省掉用户手动切 WiFi 这一步（这是当前配网流程中最大的困惑点）。微信小程序 SDK 从基础库 2.7.0 起支持 `wx.connectWifi`，需用户授权位置权限（Android）。

#### 5.2.7 小程序构建验证

```bash
cd esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile

# type check
npx vue-tsc --noEmit

# 编译
npx uni build --platform mp-weixin

# 上传
"/c/Users/zhugu/微信web开发者工具/cli.bat" upload \
  --project "$(pwd)/dist/build/mp-weixin" \
  --v "3.9.0" \
  -d "LiMa 瘦身版：对话走小智云，绘图走 DLC"
```

---

## 6. MCP 接入部署（两种确定模式）

### 6.1 模式 A：小智官方云直连（推荐）

**证据链：**
1. 小智官方控制台地址为 `https://xiaozhi.me`（非 `xiaozhi.dev`，后者为文档/营销站）。
2. 控制台路径：智能体 → 配置角色 → 右下角「MCP 接入点」。
3. 官方云直接给出 MCP endpoint URL：`wss://api.xiaozhi.me/mcp/?token=<JWT>`。
4. 第三方 Home Assistant / MCP 桥接项目（`mac8005/xiaozhi-mcp-ha`、`shawn996/mcp_ha_xiaozhi`）和 `xiaozhi-client` 文档均证实该 endpoint 为官方云原生 MCP 接入点。
5. 自定义 MCP 服务以**客户端**身份通过 WebSocket 连入该 endpoint；小智云收到 tool call 后转发到该 WebSocket 连接。

**数据流：**

```text
小智云（xiaozhi.me）←──WSS──→ dlc_mcp_client（dlc_mcp/mcp_pipe.py）
                                      │
                                      ▼
                              dlc_mcp/server.py
                                      │
                                      ▼
                              dlc_api / dlc_core
```

**部署步骤：**

1. 登录小智官方控制台 `https://xiaozhi.me`，进入目标智能体 → 配置角色 → 右下角「MCP 接入点」。
2. 复制官方给出的 MCP endpoint URL，形如：
   ```text
   wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJIUzI1NiIs...
   ```
3. 在 VPS/本地启动 `dlc_mcp`，配置环境变量：
   ```bash
   export MCP_ENDPOINT="wss://api.xiaozhi.me/mcp/?token=eyJ..."
   export DLC_API_URL="http://127.0.0.1:8080"
   python dlc_mcp/mcp_pipe.py dlc_mcp/server.py
   ```
4. 启动 `dlc_api`（生产环境仅 bind 127.0.0.1，见 §13.1 S9；公网经 nginx TLS 终止反代）：
   ```bash
   python -m uvicorn dlc_api.app:app --host 127.0.0.1 --port 8080
   ```
5. 在控制台保存 MCP 接入点；小智云 LLM 即可发现 `dlc.write_text` / `dlc.draw_generated` / `dlc.get_device_status`（`dlc.get_plotter_knowledge` 可选）。

### 6.2 模式 B：自托管 mcp-endpoint-server（私有化场景）

**证据链：**
1. 官方仓库：`https://github.com/xinnan-tech/mcp-endpoint-server`。
2. 配置文件名：`data/.mcp-endpoint-server.cfg`（首次启动若缺失，仓库根目录的 `mcp-endpoint-server.cfg` 模板会被复制到 `data/`）。
3. 配置格式：Python `configparser` INI，固定 section：`[server]`、`[websocket]`、`[security]`、`[logging]`。
4. 连接方向：自定义 MCP 服务作为**客户端**连到 `/mcp_endpoint/mcp/`；小智设备/云作为客户端连到 `/mcp_endpoint/call/`。
5. 接入器参考：上游 `78/mcp-calculator` 的 `mcp_pipe.py` 把 stdio MCP server 桥接到 WebSocket。

**数据流：**

```text
小智云 / 设备 ←──WSS──→ mcp-endpoint-server ←──WSS──→ dlc_mcp_client（mcp_pipe.py）
                                                                 │
                                                                 ▼
                                                         dlc_mcp/server.py
                                                                 │
                                                                 ▼
                                                         dlc_api / dlc_core
```

**部署步骤：**

1. 克隆并启动 mcp-endpoint-server：
   ```bash
   git clone https://github.com/xinnan-tech/mcp-endpoint-server
   cd mcp-endpoint-server
   # 复制模板配置（如仓库根目录存在 mcp-endpoint-server.cfg）
   cp mcp-endpoint-server.cfg data/.mcp-endpoint-server.cfg
   # 按需修改 data/.mcp-endpoint-server.cfg
   python main.py
   ```

2. 配置文件示例（`data/.mcp-endpoint-server.cfg`）：
   ```ini
   [server]
   host = 0.0.0.0
   port = 8004
   debug = false
   log_level = info
   key = change-me-in-production

   [websocket]
   ping_interval = 20
   ping_timeout = 10

   [security]
   allowed_origins = *

   [logging]
   level = info
   ```

3. 启动 dlc_mcp 接入器：
   ```bash
   export MCP_ENDPOINT="ws://your-server:8004/mcp_endpoint/mcp/?token=change-me-in-production"
   export DLC_API_URL="http://127.0.0.1:8080"
   python dlc_mcp/mcp_pipe.py dlc_mcp/server.py
   ```

4. 若使用小智官方云，需在 `https://xiaozhi.me` 控制台注册自托管接入点：
   ```text
   wss://your-server:8004/mcp_endpoint/mcp/?token=change-me-in-production
   ```
   若使用自托管 `xiaozhi-esp32-server`，则在该服务器配置接入点 URL。

5. 启动 `dlc_api`（S9：仅监听 127.0.0.1，公网经 nginx TLS 终止）：
   ```bash
   python -m uvicorn dlc_api.app:app --host 127.0.0.1 --port 8080
   ```

### 6.3 模式选择决策表

| 维度 | 模式 A：官方云直连 | 模式 B：自托管接入点 |
|------|-------------------|---------------------|
| 运维负担 | 最低，无需维护 mcp-endpoint-server | 需维护一台 mcp-endpoint-server |
| 网络要求 | dlc_mcp 能访问 `api.xiaozhi.me` | 小智云/设备能访问自托管服务器 |
| 私有化 | 不支持 | 支持 |
| 官方云兼容性 | 原生支持 | 需在控制台注册第三方接入点 |
| 推荐场景 | 默认推荐 | 私有化部署或官方云直连受限时 |

**默认选择：模式 A。** 只有以下情况才启用模式 B：
- 私有化网络无法访问 `api.xiaozhi.me`；
- 小智官方云在某一阶段限制第三方 MCP 接入点（当前无此迹象）；
- 需要同时接入多个自托管小智服务器（非官方云）。

### 6.4 配置项汇总

| 配置 | 模式 A 值 | 模式 B 值 | 说明 |
|------|----------|----------|------|
| 小智控制台 | `https://xiaozhi.me` | `https://xiaozhi.me` 或自托管后台 | 注册/获取 MCP 接入点 |
| MCP endpoint | `wss://api.xiaozhi.me/mcp/?token=<JWT>` | `ws(s)://your-server:8004/mcp_endpoint/mcp/?token=<key>` | dlc_mcp 客户端连接目标 |
| mcp-endpoint-server 监听地址 | 不适用 | `0.0.0.0:8004`（以 `data/.mcp-endpoint-server.cfg` 为准） | 自托管模式必填 |
| dlc_api 地址 | `http://127.0.0.1:8080` | `http://127.0.0.1:8080` | 本地/同机 |
| `dlc_mcp/mcp_pipe.py` | 模式 A/B 通用 | 模式 A/B 通用 | WebSocket MCP 桥接器 |

### 6.5 证据来源清单

- 小智官方控制台：`https://xiaozhi.me`
- 小智官方文档站：`https://xiaozhi.dev/docs/`（仅文档，不用于控制台操作）
- 小智自托管服务器源码（链式调用证据）：`https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/main/main/xiaozhi-server/core/connection.py`（`MAX_DEPTH=5`、`_handle_function_result()`、`chat(depth+1)`）
- mcp-endpoint-server 源码：`https://github.com/xinnan-tech/mcp-endpoint-server`
- mcp-calculator 接入器参考：`https://github.com/78/mcp-calculator`（`mcp_pipe.py`）
- 第三方桥接实现：`mac8005/xiaozhi-mcp-ha`、`shawn996/mcp_ha_xiaozhi`
- 固件 HTTP 抽象先例：`esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc:211`、`mcp_server.cc:209`、`assets.cc:436`

---

## 7. 实施阶段（详细）

### P0：决策验证与保护网（1-2 天）

#### P0.1 聚焦测试矩阵（已完成 ✅）

107 个测试全部 GREEN。

#### P0.2 小智云 MCP 接入验证

**验证目标：**
1. 小智官方云 `xiaozhi.me` 控制台能正常生成 MCP endpoint（`wss://api.xiaozhi.me/mcp/?token=...`）。
2. `dlc_mcp` 通过 `mcp_pipe.py` 以客户端身份连上官方云 MCP endpoint。
3. 小智云 LLM 能发现并调用 `dlc.write_text` / `dlc.draw_generated`。
4. 确认 LLM 在拿到服务端 tool 结果后，是否会继续调用设备端低层执行 tool
   （`self.motor.run_path`），或改走固件高层 tool（`self.plotter.write_text` / `self.plotter.draw_generated`）。
   - **代码层面**：官方自托管服务器 `xinnan-tech/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py` 已支持多轮 tool call（`MAX_DEPTH=5`，`chat(depth+1)`），架构上无障碍。
   - **实测层面**：官方云为闭源服务，需用真实账号验证 LLM 在真实 prompt/模型下的实际行为。
5. （仅在模式 B 时）`mcp-endpoint-server` 能转发外部 Python MCP 服务。

**验证步骤（模式 A：官方云直连，默认）：**
1. 登录 `https://xiaozhi.me` → 智能体 → 配置角色 → MCP 接入点，复制 endpoint URL。
2. 本地启动最小 MCP 服务 `dlc_mcp/server.py`（暴露 `dlc.echo` 用于联调）。
3. 运行 `dlc_mcp/mcp_pipe.py` 并设置 `MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...`。
4. 在控制台保存接入点。
5. 对小智设备说"测试 echo"。
6. 确认 LLM 能调用 `dlc.echo` 并收到返回值。
7. 替换为真实 `dlc.write_text` / `dlc.draw_generated`，验证 LLM 调用路径。

**链式调用实测步骤：**
1. 注册 `dlc.write_text` 和 `self.motor.run_path` 两个 tool；`self.plotter.write_text` 作为策略一的独立对照入口。
2. 对设备说"写你好"。
3. 查看日志：
   - 若出现 `dlc.write_text` → `self.motor.run_path` 两次 tool call → 路径 A（纯 MCP）可用，可采用实现策略二（§4.2 备选，依赖云端链式调用）。
   - 若只出现一次 tool call，且 LLM 转而调用 `self.plotter.write_text` → 仍可完成任务，但说明模型偏好策略一。
   - 若只出现一次 tool call，且未触发任何设备端执行 tool → 必须采用实现策略一（固件端 `self.plotter.write_text` / `self.plotter.draw_generated` 内部调 dlc_api）。
4. 无论实测结果如何，**默认先实现策略一**（对 LLM 行为不敏感），路径 A 实测成功并确认稳定后再评估是否切换到实现策略二。

**验证步骤（模式 B：自托管 mcp-endpoint-server）：**
1. 克隆 `xinnan-tech/mcp-endpoint-server`。
2. 配置 `data/.mcp-endpoint-server.cfg` 并启动。
3. 运行 `dlc_mcp/mcp_pipe.py` 并设置 `MCP_ENDPOINT=ws://your-server:8004/mcp_endpoint/mcp/?token=...`。
4. 在 `https://xiaozhi.me` 控制台注册自托管接入点（或修改自托管 `xiaozhi-esp32-server` 配置）。
5. 重复模式 A 的 5-7 步及链式调用实测步骤。

#### P0.3 瘦身基线文档

创建 `docs/LIMA_SLIMDOWN_BASELINE_CN.md`，列出保留/删除清单。

### P1：新增轻量入口（2-3 天）

#### P1.1 dlc_core facade

```python
# dlc_core/__init__.py
# Phase 1: facade 调用旧模块
from device_gateway.intent import resolve_voice_task as parse_intent
from device_gateway.path_pipeline import text_to_path, svg_path_to_motion as svg_to_motion, precheck_draw_motion_path as precheck_path
from device_gateway.device_write_handler import handle_device_write as handle_write
from device_gateway.device_draw_handler import handle_device_draw as handle_draw
from device_gateway.path_validator import validate_capability_params, validate_route_policy
from device_gateway.safety import DEFAULT_WORKSPACE_MM
from device_gateway.path_validator import MAX_PATH_POINTS
```

#### P1.2 dlc_api

新建 `dlc_api/app.py` + `dlc_api/routes.py`。

#### P1.3 dlc_mcp

新建 `dlc_mcp/server.py` + `dlc_mcp/schemas.py` + `dlc_mcp/mcp_pipe.py`。
`mcp_pipe.py` 是 MCP WebSocket 接入器：
- 模式 A（官方云直连）：连接 `wss://api.xiaozhi.me/mcp/?token=<JWT>`；
- 模式 B（自托管）：连接 `ws://your-server:8004/mcp_endpoint/mcp/?token=<key>`。

详见 §6。

#### P1.4 测试

```bash
python -m pytest tests/dlc/ -v
python -m uvicorn dlc_api.app:app --port 8080 &
curl -sf http://127.0.0.1:8080/health
curl -sf -X POST http://127.0.0.1:8080/dlc/tasks/preview -H "Content-Type: application/json" -d '{"type":"write_text","text":"你好"}'
```

### P2：切换生产入口（2-3 天）

#### P2.1 server_dlc.py

新建 `server_dlc.py`，只注册 dlc_router + 保留的 device 路由。

#### P2.2 部署脚本

`scripts/deploy_unified.py` 新增 `--slice dlc-core`。

#### P2.3 生产切换

```bash
# VPS 上
systemctl stop lima-router
systemctl start dlc-drawing  # 新 systemd unit
curl http://127.0.0.1:8080/health
```

#### P2.4 `shadow_store` 部署策略（P2 必须明确）

`device_intelligence/shadow.py` 的 `shadow_store` 当前为内存 `dict` + `threading.RLock`（证据：`shadow.py` 使用内存字典），**多 `dlc_api` 实例间不共享**。P2 必须二选一：

| 方案 | 描述 | 适用场景 | 工作量 |
|------|------|---------|--------|
| **A：单实例部署（推荐）** | 阿里云 `47.112.162.80` 只运行一个 `dlc_api` 进程；nginx 反代到 `127.0.0.1:8080` | 默认 P2；用户量/并发在单实例承受范围内 | 零额外工作 |
| B：`shadow_store` → Redis | 把 `shadow_store` 后端改为 Redis，所有实例共享 | 未来需要多实例水平扩展时 | 2-3 天；需重写 `shadow.py` 读写逻辑 |

**P2 默认采用方案 A。** 理由：
- 遵循 Ponytail 最小变更原则；
- 当前 `dlc_api` 主要是 I/O 轻量的路径生成 + 任务下发，单实例足以支撑初期用户量；
- 避免 P2 引入 Redis 迁移风险。

**方案 A 的部署约束（写入 P2 checklist）：**
- `dlc_api` systemd unit 只启动 1 个 worker；
- nginx 只反代到 `127.0.0.1:8080`，不配置 upstream 多后端；
- 升级/重启时先停旧实例再启新实例，避免双实例同时运行导致 shadow 分裂。

**方案 B 的触发条件：**
- 单实例 CPU/内存持续 >70%；
- 需要 99.9% 可用性，不能因升级/重启中断；
- 用户量增长到需要多实例负载均衡。

> 触发方案 B 前，先完成 `shadow_store` Redis 化改造，并补充跨实例一致性测试。

#### P2 完成标准

- 旧 `server.py` 仍可启动（legacy 兼容）
- 父仓库 `D:/QWEN3.0` 更新 `esp32S_XYZ` 子模块指针并提交（`git add esp32S_XYZ && git commit`）
- `dlc_api` 以单实例运行（P2 默认），或 `shadow_store` 已迁移 Redis（如提前实施方案 B）

### P3：迁移纯函数（3-5 天）

逐个从 `device_gateway/` 迁移到 `dlc_core/`，每迁移一个就更新测试 import。

### P4：物理删除（2-3 天）

按 §3.6 清单分批删除，每批后跑聚焦测试。

### P5：收尾（1-2 天）

更新文档、依赖、部署脚本。

---

## 8. 测试策略

### 8.1 服务端测试矩阵

| 测试类别 | 测试文件 | 数量 | 说明 |
|---------|---------|------|------|
| 绘图算法 | `test_hershey_font.py` | ~10 | 字体渲染 |
| 绘图算法 | `test_text_to_path.py` | ~8 | 文字→路径 |
| 绘图算法 | `test_skeleton_prune.py` | ~5 | 骨架提取 |
| 意图解析 | `test_device_intent_hardening.py` | ~8 | 意图分类 |
| 路径管线 | `test_device_gateway_path_pipeline.py` | ~15 | 文本/SVG→路径 |
| 路径校验 | `test_device_gateway_path_validator.py` | ~12 | 安全校验 |
| 写字处理 | `test_device_gateway_write_handler.py` | ~6 | 写字全流程 |
| 绘图处理 | `test_device_draw_handler*.py` | ~15 | 绘图全流程 |
| 任务投影 | `test_task_creation_draw_generated.py` | ~3 | 意图→任务 |
| 边界校验 | `test_draw_path_bounds.py` | ~4 | 运动边界 |
| **合计** | | **~107** | 当前全绿 ✅ |

### 8.2 冒烟测试（P2 后）

```bash
python -m uvicorn dlc_api.app:app --port 8080
curl -sf http://127.0.0.1:8080/health
curl -sf -X POST http://127.0.0.1:8080/dlc/tasks/preview -H "Content-Type: application/json" -d '{"type":"write_text","text":"你好"}'
curl -sf -X POST http://127.0.0.1:8080/dlc/tasks/preview -H "Content-Type: application/json" -d '{"type":"draw_generated","prompt":"星星"}'
# 图库图片矢量化（image_url 为图库下载 URL）
curl -sf -X POST http://127.0.0.1:8080/dlc/tasks/preview -H "Content-Type: application/json" -d '{"type":"draw_from_image","image_url":"https://example.com/image.png"}'
# 设备状态查询（device_id 替换为真实设备）
curl -sf http://127.0.0.1:8080/dlc/devices/DEVICE_ID/status
```

### 8.3 固件测试

```cpp
// test_dlc_plotter_tools.cpp
TEST(DlcPlotterTools, WriteTextRegistered) {
    auto& mcp = McpServer::GetInstance();
    auto tools = mcp.GetToolList();
    EXPECT_TRUE(tools.contains("self.plotter.write_text"));
}

TEST(DlcPlotterTools, DrawGeneratedRegistered) {
    auto& mcp = McpServer::GetInstance();
    auto tools = mcp.GetToolList();
    EXPECT_TRUE(tools.contains("self.plotter.draw_generated"));
}
```

### 8.4 小智云联调验收

- [ ] 小智云普通对话正常回复
- [ ] 说"写你好"时触发 `dlc.write_text` 或 `self.plotter.write_text`
- [ ] 说"画一颗星星"时触发 `dlc.draw_generated` 或 `self.plotter.draw_generated`
- [ ] 说"画这张图"并选择图库图片时触发 `dlc.draw_from_image` 或小程序 `draw_from_image`
- [ ] 设备收到路径，假 U1 返回 done
- [ ] 路径越界、点数超限、空 SVG、危险指令被拒绝
- [ ] 小程序"一键写字"按钮正常下发
- [ ] 小程序"一键画图"按钮正常下发
- [ ] 小程序"从图库选图绘图"按钮正常下发
- [ ] 小程序任务状态 WebSocket 正常推送

### 8.5 CodeGraph 死代码审计

```bash
codegraph sync .
python scripts/codegraph_orphans.py --fanin
```

---

## 9. 风险与回滚

| 风险 | 概率 | 影响 | 处理 |
|------|------|------|------|
| 小智官方云 MCP 接入点策略变更 | 低 | 高 | 默认模式 A；如受限，回退到模式 B（自托管 mcp-endpoint-server） |
| 小智云 LLM 不连续调用服务端+设备端 tool | 中 | 高 | P0 实测；默认采用实现策略一（固件端 tool 直接调 dlc_api），不依赖 LLM 链式行为 |
| 一次性删除导致生产不可用 | 低 | 高 | Strangler Fig：先建新入口，旧入口保留 |
| 绘图模块隐含依赖 LiMa 路由/记忆 | 中 | 中 | P3 按测试迁移纯函数，先 facade 后替换 import |
| 固件 HTTPS POST 在绘图大 payload 下内存不足 | 低 | 中 | 复用现有 `CreateHttp()` 抽象；dlc_api 返回路径 JSON 控制在 ≤100 KB；超时 5s |
| 小程序用户已习惯 chat 功能 | 低 | 低 | chat 页面标记 deprecated，不主动删除 |
| Telegram 图盘速率/容量受限 | 低 | 中 | 默认保留；达到限制时迁移到 S3/MinIO/R2，接口不变 |
| 高并发下 Redis broker 或 dlc_api 单实例瓶颈 | 低 | 中 | dlc_api 无状态可水平扩展；Redis 队列原子操作；shadow_store 可迁移到 Redis |
| 硬件运动安全事故 | 低 | 高 | 保留 `path_validator`，真机验证必须单独做 |
| `wx.connectWifi` 在部分 Android 10+ / iOS 设备上无法自动连接 SoftAP | 中 | 高 | 一键配网 UI 必须提供"手动连接 DLC-XXXXXX"fallback；`maunal:true` 跳转系统 WiFi 作为次级 fallback |
| `78/esp-wifi-connect` 的 `/submit` 不支持透传 pair_token | 中 | 中 | 默认方案已确定为 pair_token 预绑定，P1 必须 fork 组件扩展 `/submit` + 新增 `/device-info`；无法 fork 时回退到最小改动方案 |

### 回滚策略

1. **P0-P1**：无回滚需要（只新增文件，不删旧文件）
2. **P2**：`systemctl stop dlc-drawing && systemctl start lima-router`（切回旧入口）
3. **P3**：`git revert` 迁移提交，恢复 `device_gateway/` import
4. **P4**：`git revert` 删除提交（文件在 git 历史中）
5. **固件**：`self.upgrade_firmware` 回滚到旧版本
6. **小程序**：微信后台提交旧版本审核

---

## 10. 验收标准

### 10.1 服务端

- [x] `dlc_api` 可独立启动，`/health` 返回 200
- [x] `dlc_api` `/dlc/tasks/preview` 正确返回写字/绘图/图片矢量化预览
- [x] `dlc_api` `/dlc/tasks/dispatch` 正确下发任务
- [x] `dlc_api` `/dlc/devices/{device_id}/status` 返回正确在线/工作/任务状态
- [x] `dlc_mcp` 可被 MCP 客户端调用 `dlc.write_text` / `dlc.draw_generated` / `dlc.draw_from_image`
- [x] `dlc_mcp` 可被 MCP 客户端调用 `dlc.get_device_status`（`dlc.get_plotter_knowledge` 可选）
- [x] 生产入口不再注册 chat/admin/voice/provider 路由
- [ ] 任务失败自动重试/死信/通知链路可验证
- [x] P2 单实例 `dlc_api` + Redis 任务队列场景可稳定运行
- [ ] P4（或后续扩展阶段）完成 `shadow_store` Redis 化后，多 `dlc_api` 实例 + Redis 任务队列并发场景可验证（至少 2 实例 + 2 设备）
- [x] 聚焦测试 55 个全绿（`pytest -k dlc`）
- [x] `python -m pytest --tb=short -q` 无 ImportError（1549 passed / 3 skipped / 0 failed）
- [x] repo stats 文件数下降 40%+（P5 删除 903 文件 / 171k 行）

### 10.2 固件

- [x] `self.plotter.write_text` 工具已注册
- [x] `self.plotter.draw_generated` 工具已注册
- [x] 低层执行 tool `self.motor.run_path` 保持可用，并与链式调用路径兼容
- [ ] 假 dlc_api mock 测试通过
- [ ] CI `firmware-dlc-tools` job 绿灯
- [ ] 真机验证：语音"写你好"→ 设备执行写字
- [ ] 真机验证：语音"画星星"→ 设备执行绘图
- [ ] 路径越界指令被拒绝
- [ ] **防呆验证：设备执行 A 时语音下发 B，B 返回 `device is busy`，LLM 提示"正在忙请稍等"**
- [ ] **防呆验证：设备执行 A 时语音下发 `pause`，pause 正常执行（不受 busy 锁限制）**
- [ ] **防呆验证：设备执行 A 时小程序按下写字，返回 `device_busy` 而不下发**

### 10.3 小程序

- [x] `vue-tsc --noEmit` 0 errors
- [x] `uni build --platform mp-weixin` 成功
- [x] `vitest` 全绿（4 passed）
- [x] `check-i18n-keys.mjs` 通过（806 keys）
- [x] 微信开发者工具 CLI 上传成功（v3.9.0, 1.2MB）
- [ ] 设备列表、任务下发、状态 WebSocket 正常
- [ ] 图库上传/选择/删除功能正常
- [ ] 从图库选图后调 `draw_from_image` 生成路径并下发成功
- [x] chat 页面已物理删除（对话走小智云，不再需要本地 chat 页面）
- [ ] **一键配网：SoftAP 自动连热点 → 选 WiFi → 输密码 → 一键配网 → 成功提示**
- [ ] **一键配网：wx.connectWifi 自动连接 DLC-XXXXXX 热点（用户无需手动切 WiFi）**
- [ ] **一键配网：wx.connectWifi 失败时提供手动连接 fallback（Android 10+ / iOS 兼容）**
- [ ] **一键配网：pair-status 轮询显示配网成功/失败**
- [x] **固件/小程序 SoftAP SSID 前缀统一为 DLC-XXXXXX**
- [x] 版本号 3.9.0 / 390

### 10.4 小智云

- [ ] 模式 A：`dlc_mcp` 通过 `wss://api.xiaozhi.me/mcp/?token=...` 以客户端身份接入成功
- [ ] 模式 B（如启用）：`mcp-endpoint-server` 运行正常，`dlc_mcp` 以客户端接入成功
- [ ] `dlc.write_text` / `dlc.draw_generated` / `dlc.draw_from_image` 工具已注册并可被调用
- [ ] `dlc.get_device_status` 工具已注册并可被调用；问"绘图机在干嘛"能返回状态
- [ ] 普通对话正常（走小智云 LLM）
- [ ] 写字/绘图意图识别正确并调用工具
- [ ] 用户问"绘图机为什么不走了"等知识类问题时，能基于角色 prompt / `dlc.get_plotter_knowledge` 回答
- [ ] 固件端 `self.plotter.write_text` / `self.plotter.draw_generated` 调用 dlc_api 生成并执行路径成功

### 10.5 文档

- [x] `STATUS.md` 更新项目定位
- [x] `progress.md` 记录删减批次
- [x] `.env.example` 更新（含 `MCP_ENDPOINT` / `DLC_API_URL`）
- [x] `AGENTS.md` / `CLAUDE.md` 更新
- [x] 部署文档更新（`deploy/aliyun/dlc-mcp.service` + `install_dlc_mcp.sh`）
- [x] `docs/xiaozhi-cloud/` 小智文档缓存完整

---

## 11. 工作量估算

| 阶段 | 工作量 | 关键产出 |
|------|--------|---------|
| P0 决策验证 | 1-2 天 | 小智云接入确认 + 基线文档 |
| P1 轻量入口 | 2-3 天 | dlc_api + dlc_mcp 可运行 |
| P1 服务端安全加固 | 2-3 天 | verify_dlc_api_token + per-device 鉴权 + RateLimiter + SSRF 防护 + Redis schema gate + task_id UUID |
| P2 切换生产 | 2-3 天 | server_dlc.py + 部署 + 冒烟 |
| P3 迁移纯函数 | 3-5 天 | dlc_core 不依赖 device_gateway |
| P4 物理删除 | 2-3 天 | 大模块删除 + 测试清理 |
| P5 收尾 | 1-2 天 | 文档 + 依赖 + repo stats |
| 固件改造 | 3-4 天 | 2 个新 MCP tool + NVS token + motion_busy + path 限制 + json 异常保护 + HTTPS 强制 + 测试 |
| 小程序改造 | 2-3 天 | 删除 chat + 简化 + 一键配网 + 上传 |
| 固件配网统一 | 0.5-1 天 | SoftAP/BluFi SSID 前缀统一为 DLC + 激活回调 |
| 服务端配网去重 | 0.5-1 天 | pair/provision 端点去重 + pair-status 查询 |
| **合计** | **19-32 天** | |

> **注意：** 固件改造从原估 1-2 天上调至 3-4 天，因安全审计新增 NVS token 读取、motion_busy 防呆、path 段数/长度限制、json::parse 异常保护、HTTPS 强制校验等工作项。服务端安全加固为新增阶段（2-3 天）。小程序改造因一键配网改造上调至 2-3 天。

---

## 12. 复核修正记录（2026-07-05）

> 以下问题由架构复核发现并已修正：

| 编号 | 严重度 | 问题 | 修正 |
|------|--------|------|------|
| B1 | 🔴 | image_fallback 依赖 routes/images.py（已列入删除） | 区分两种图片能力：① `device_gateway/image_fallback.py` 是 DashScope 生图失败时的文生图降级链路，随 `routes/images.py` 一起删除；② 图库图片矢量化能力必须保留，由 `xiaozhi_drawing/svg_converter.py` 提供，新增 `dlc.draw_from_image` MCP tool 和 `draw_from_image` API type 处理图库/用户上传图片 |
| B2 | 🔴 | 删除 dashscope 与保留 draw_generated 矛盾 | dashscope 标注保留，仅 dlc_api 使用 |
| B3 | 🔴 | path_validator 依赖 device_intelligence 未提及 | 保留清单补入 device_intelligence/ 和 model_routing/protocol_families |
| B4 | 🔴 | MAX_PATH_POINTS 来源和值错误（运动安全边界） | 修正 facade import 和常量值（200/100x100x20） |
| W1 | 🟠 | mcp 依赖未纳入部署清单 | 保留依赖追加 mcp>=1.6.0 |
| W3 | 🟠 | dlc_core 声称纯函数但含网络 I/O | 定位修正为"纯路径算法 + 薄封装" |
| W4 | 🟠 | 删除 chat 页面未处理 pages.json | 改动表补入 pages.json |
| W5 | 🟠 | goChat/goDigitalHuman 在 composables 不在 vue | 改动表补入 useHomeNavigation.ts |
| W7 | 🟠 | 子模块指针 bump 未提及 | P2 完成标准补入子模块指针提交 |
| 安全 | 🟠 | dlc_api dispatch 无鉴权 | 补入 device token 鉴权 |
| B5 | 🔴 | mcp-endpoint-server 架构方向错误 | 修正为 dlc_mcp 以客户端接入；§6 给出模式 A（官方云直连）和模式 B（自托管）两种确定部署方式 |
| B6 | 🔴 | 小智官方云 `xiaozhi.dev` 与 `mcp-endpoint-server` 的兼容性未验证 | 官方控制台地址修正为 `https://xiaozhi.me`；官方云提供原生 MCP endpoint `wss://api.xiaozhi.me/mcp/?token=...`，无需 mcp-endpoint-server 即可接入（模式 A） |
| B7 | 🔴 | `dlc.draw_generated` 工具直接依赖 device_draw_handler 的 DashScope AI 生图 | 明确 `dlc.draw_generated` MCP 工具不使用 DashScope；DashScope 仅通过小程序 HTTP 路径 `/dlc/tasks/preview?type=draw_generated` 保留 |
| B8 | 🔴 | 文档中固件 outbound HTTP 可行性描述错误 | 已确认 `u8-xiaozhi/main/ota.cc`、`mcp_server.cc`、`assets.cc` 等存在 `CreateHttp()` 先例；§4.2 示例改为复用该抽象 |
| B9 | 🔴 | `mcp-endpoint-server` 配置格式与控制台地址不确定 | 已查证：配置文件 `data/.mcp-endpoint-server.cfg`、INI 格式、固定 section；控制台为 `https://xiaozhi.me`；证据写入 §6.1/§6.2/§6.5 |
| W8 | 🟠 | dlc_core 接口命名与源码不符 | `parse_intent` 保留为 facade 名称（底层对应 `parse_command`/`resolve_voice_task`）；`svg_to_motion`→`svg_path_to_motion`；`precheck_path` 保留 facade 别名（底层 `precheck_draw_motion_path`） |
| W9 | 🟠 | 固件文件路径缺少 `u8-xiaozhi/main/` 前缀 | 所有路径已补全 |
| W10 | 🟠 | MAX_PATH_POINTS 在多个旧模块中定义不一致 | 文档注明 P3 需统一收敛到 dlc_core，权威值 200 |
| W11 | 🟠 | `path_validator.py` 依赖 `model_routing.py`/`protocol_families.py` 未在保留清单体现 | 保留清单已补入 |
| W12 | 🟠 | `mcp-endpoint-server` 真实配置文件名/格式需对照仓库源码确认 | 已确认并写入 §6.2 |
| B10 | 🔴 | 小智云是否支持服务端 tool → 设备端 tool 链式调用不确定 | 已读取官方自托管服务器源码 `xinnan-tech/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py`：`MAX_DEPTH=5` + `_handle_function_result()` 写回 `role="tool"` + `chat(depth+1)` 递归，证明架构原生支持多轮 tool call。官方云大概率一致，但仍需 P0 实测确认 |
| C1 | 🟡 | 5 个业务运营关键问题未闭环：图盘、状态监控、知识问答、高并发、任务失败 | 新增 §1.6 逐项闭环：① Telegram 图盘保留并给出容量/迁移方案；② 新增 `dlc.get_device_status` MCP tool 与 `/dlc/devices/{device_id}/status` API；③ 知识问答优先使用小智控制台角色 prompt，可选 `dlc.get_plotter_knowledge`；④ 并发依赖无状态 dlc_api + Redis 原子队列；⑤ 失败处理复用现有状态机 + 自动重试 + 死信 + 微信订阅通知 |

> 复核中已用权威证据消除的不确定性：
> - W2: 固件出站 HTTP：已用 `ota.cc:211`、`mcp_server.cc:209`、`assets.cc:436` 证实 `Board::GetInstance().GetNetwork()->CreateHttp()` 可用。
> - W6: `task_creation` 依赖 `device_policy/async_utils`：属于 P3 迁移实现细节，不在架构不确定性范围；P3 按接口重新实现精简版。
> - S4: `dlc.*` MCP 工具命名：小智官方云对 tool 名无全局注册表限制，命名由 MCP server 的 `tools/list` 决定；文档保持 `dlc.write_text` / `dlc.draw_generated`。
> - W12: `mcp-endpoint-server` 配置：已确认 `data/.mcp-endpoint-server.cfg`、INI 格式、固定 section。
> - B10: 链式调用：官方自托管服务器代码已证明支持多轮 tool call；剩余唯一不确定的是官方云真实 prompt/模型下的实际 LLM 行为，属于 P0 实测项而不再是不确定性。文档已将 §4.2 的"设计方案 A/B"重命名为"实现策略一/二"，避免与 §2.3"路径 A/B/C"混淆。

### 第二轮深度复核修正记录（2026-07-06）

> 以下问题由第二轮源码级深度复核发现并已修正：

| 编号 | 严重度 | 问题 | 修正 | 证据 |
|------|--------|------|------|------|
| D1 | 🔴 | `shadow_store` 内存存储导致多 `dlc_api` 实例状态不一致 | §1.6.4 扩展表格列和 P4 后续扩展路径标注为 P2 前置任务；P2 部署时必须先迁移 Redis 或单实例 | `device_intelligence/shadow.py`: `threading.RLock` + `dict` |
| D2 | 🔴 | §1.6.3 角色 prompt 示例写"可以帮用户查询设备状态"，诱导 LLM 编造状态 | 改为强制指令：**必须调用 `dlc.get_device_status` 工具获取实时数据，不要自行推测或编造** | AI 痛点：LLM 会跳过 tool 直接编造答案 |
| D3 | 🟠 | §1.3 小智官方云称"免费"过于绝对 | 改为"基础额度免费"（付费增值以官方公告为准） | 小智官方未明确承诺永久全免费 |
| D4 | 🟠 | §1.6.5 失败处理只覆盖运行阶段 `motion_event` failed | 新增阶段 A（dispatch 下发超时/失败）处理流程 | `device_gateway/redis_store.py`: dispatch_task 超时 |
| D5 | 🟠 | §1.6.1 Telegram "20 msg/s" 未说明是官方限制还是经验值 | 补充官方限制证据：全局 30 msg/s，同会话 1 msg/s；LiMa 保守取 20 msg/s | [Telegram Bot API](https://core.telegram.org/bots/api#handling-errors), [GitHub tdlib#3034](https://github.com/tdlib/td/issues/3034) |
| D6 | 🔴 | B10 链式调用证据不完整，缺少 `Action.REQLLM` 代码证据 | §2.3 补充完整代码证据链表格（6 行证据），引用具体文件和行 | `unified_tool_handler.py`:53, `mcp_endpoint_executor.py`:53, `mcp_executor.py`:53, `connection.py`:941,1270,1357 |
| D7 | 🟠 | `dlc.dispatch_task` MCP tool 对 LLM 暴露增加幻觉风险 | 从 MCP tool 列表和 `call_tool` 移除；保留在 HTTP API（`/dlc/tasks/dispatch`）供小程序/外部调用 | AI 痛点：tool 越多模型越容易选错 |
| D8 | 🟠 | 错误码表混用现有和设计新增，未区分来源 | 补充"来源"列：现有 ✅ / 设计新增 | `device_intelligence/recovery.py` 现有错误码清单 |
| D9 | 🟡 | `draw_from_image` 固件端处理路径不清晰 | 新增表格说明 `draw_from_image` 语音路径走策略二（LLM 链式调 `dlc.draw_from_image` → `self.motor.run_path`），固件端无需新增 tool | Ponytail 最小实现 |

> 第二轮复核已消除的不确定性：
> - **平台能力链式调用**：已从官方源码确认完整调用链 `Action.REQLLM` → `_handle_function_result` → `role="tool"` → `chat(depth+1)` → LLM 二次决策。不再有平台能力不确定性。
> - **剩余唯一 P0 实测项**：具体 LLM 模型是否会在拿到路径 JSON 后**主动决定**调用设备端 tool，取决于模型的 function-calling 推理能力。**默认采用实现策略一**（固件端 tool 内部调 dlc_api），不依赖 LLM 行为。

### 第三轮防呆复核修正记录（2026-07-06）

> 用户提问"设备运行过程中小智让操作设备，有防呆机制设计吗"触发此轮复核。

| 编号 | 严重度 | 问题 | 修正 | 证据 |
|------|--------|------|------|------|
| F1 | 🔴 | 固件端 `MotionExecutor` 无运动忙标志，多源并发运动任务可能导致 UART 指令交错 | 新增 §1.6.6 完整防呆设计：固件 `motion_busy_` 原子标志 + RAII guard + 服务端 pre-check + 角色 prompt 指令，三层防护 | `motion_executor.h` 无 busy 成员；`u1_protocol_client.h:102-103` 有 `uart_mutex_`/`job_mutex_` 但只保证单条原子 |
| F2 | 🔴 | 固件文件修改清单缺少 `motion_executor.h/cc` | §4.3 补入 `motion_executor.h` 新增 `motion_busy_` 成员、`motion_executor.cc` 4 个函数入口加 CAS + RAII guard | 代码审查发现遗漏 |
| F3 | 🟠 | 固件测试和验收标准缺少防呆测试项 | §4.5 补入 2 个防呆测试（并发 RunPath 拒绝、pause 不受限）；§10.2 补入 3 个防呆验收项 | 测试覆盖性检查 |

**现有防呆机制清单（已确认保留）：**

| 机制 | 代码位置 | 说明 |
|------|---------|------|
| UART 互斥锁 | `u1_protocol_client.h:102` `uart_mutex_` | 保证单条 UART 指令原子性 |
| Job 互斥锁 | `u1_protocol_client.h:103` `job_mutex_` | 保证 job 上下文原子性 |
| OTA 拦截 | `dlc_motor_control_p1_ai_board.cc:271-277` | `kDeviceStateUpgrading` 时拒绝运动任务 |
| 坐标边界双重防线 | `motion_executor.cc:223-237` | 固件端 `±500mm` 物理边界 + `isfinite` 校验 |
| Feed 范围校验 | `motion_executor.cc:47-49` | `feed ∈ [1, 20000]` |
| 相对移动 ±1mm 限制 | `dlc_motor_control_p1_ai_board.cc:197-198` | `dx/dy/dz ∈ [-1, 1]` |
| 服务端路径校验 | `device_gateway/path_validator.py` | 坐标边界 + 点数限制 + feed 限制 |
| 服务端任务队列 FIFO | `device_gateway/redis_store.py` `LMOVE` | pending → processing 原子出队 |
| 服务端重试上限 | `device_gateway_dispatch.py:84` `MAX_TASK_RETRIES = 3` | 超限进死信队列 |

### 第四轮一键配网复核修正记录（2026-07-06）

> 用户提出"登录配网问题；这个要简单方便需要在小程序端提供一键配网功能"触发此轮复核。目标：把 SoftAP 一键配网方案在固件端、小程序端、服务端三方闭环，并补充权威证据链。

| 编号 | 严重度 | 问题 | 修正 | 证据 |
|------|--------|------|------|------|
| N1 | 🔴 | §4.3 固件文件修改清单缺少 `provisioning_contract.h` / `wifi_board.cc` / `application.cc` 的配网相关项 | §4.3 已补全：① `provisioning_contract.h` 改 `DLC` 前缀；② fork `78/esp-wifi-connect` 新增 `/device-info` + 扩展 `/submit`；③ `application.cc` 新增 pair_token 绑定回调，写入 `dlc_api_token` 到 NVS | `provisioning_contract.h:9-10` 当前为 `Xiaozhi` / `Xiaozhi-Blufi`；`wifi_board.cc:58` 使用 `ProvisioningContract::kSoftApSsidPrefix` |
| N2 | 🔴 | §5.2.6 时序图错误：声称 `/submit` 可携带 `server_host` / `device_secret` / `pair_token` | 已修正：`78/esp-wifi-connect` 的 `/submit` 只解析 `ssid`/`password`；默认方案需 fork 组件扩展 `/submit` 以透传 `pair_token`，无 pair_token 透传作为 fallback | [GitHub 78/esp-wifi-connect wifi_configuration_ap.cc](https://github.com/78/esp-wifi-connect) |
| N3 | 🔴 | §5.2.6 声称 `softApSsidHint` 要"改为与固件一致"，方向反了 | 已修正：固件侧改为 `DLC` 前缀，小程序侧保持 `DLC-XXXXXX`；并补充 SSID 生成规则 `{prefix}-{mac[4]:02X}{mac[5]:02X}` | [GitHub 78/esp-wifi-connect](https://github.com/78/esp-wifi-connect) |
| N4 | 🟠 | `wx.connectWifi` 在 Android 10+ 和 iOS 的限制未说明 | §5.2.6 补充：Android 10+ 可能需 `maunal:true`；iOS 需监听 `onWifiConnected`；open 网络传空密码 | [微信官方文档](https://developers.weixin.qq.com/miniprogram/dev/api/device/wifi/wx.connectWifi.html) |
| N5 | 🟠 | 未说明 SoftAP 是 open 网络 | §4.3 证据链补充 `wifi_config.ap.authmode = WIFI_AUTH_OPEN` | [GitHub 78/esp-wifi-connect](https://github.com/78/esp-wifi-connect) |
| N6 | 🟡 | 固件激活与 pair_token 绑定的关系不清晰 | §5.2.6 已明确采用 pair_token 预绑定作为默认方案：设备连网后调用 `/devices/provision/confirm` 完成账户绑定，并在响应中获取 `dlcApiToken` 写入 NVS | `ota.cc:809` 当前激活依赖 HMAC/挑战码；`device_app_provision.py` pair_token 流程在服务端 |
| N7 | 🟠 | 未补充小程序蓝牙大数据流限制作为弃用 BluFi 的证据 | §5.2.6 新增理由：微信官方建议 `wx.writeBLECharacteristicValue` 单次写入不超过 20 字节，并行写易失败；SoftAP HTTP 更适合后续配置/OTA 场景 | [微信官方文档](https://developers.weixin.qq.com/miniprogram/dev/api/device/bluetooth-ble/wx.writeBLECharacteristicValue.html) |

> 第四轮复核后决策闭环：
> - **pair_token 预绑定作为默认方案**：复用 `routes/device_app_provision.py` 现有实现，设备连网后完成绑定并获取 per-device `dlc_api_token`。P1 必须 fork `78/esp-wifi-connect` 新增 `/device-info` + 扩展 `/submit` 透传 `pair_token`。
> - **Fallback 方案**：若 P1 无法及时 fork 组件，可回退到无 pair_token 透传的最小改动方案，但 per-device token 需通过后续 OTA 或 WS hello 交互下发。

---

## 13. 安全审计修正（2026-07-06）

> 三轮源码级安全审计（API 鉴权、固件端、MCP/SSRF/Redis）发现 18 个独立漏洞，按严重度分类如下。已全部在设计文档中给出修正方案。

### 13.1 🔴 严重漏洞（7 项，物理安全防线，P1 必须修复）

#### S1 — `verify_dlc_api_token` 未定义且共享 token 无法做 per-device 校验 ✅ 部分修复（2026-07-06）

> **状态**：`dlc_api/deps.py::verify_dlc_api_token` 已实现，DB 表 `v2_device_token` 优先、`LIMA_DEVICE_TOKENS` env 为 dev/应急 fallback。**2026-07-06 补齐**：`v2_device_token` DDL（表 + `token_hash` 唯一索引）已加入 `device_logic/db_migrations.py::_DDL_STATEMENTS`，每次 bootstrap 幂等创建，生产不再永远回退 env。测试：`tests/test_v2_device_token_migration.py`。**待办**：per-device token 首次激活签发 + 轮换（Q-07，P2/P3）。

**问题：** 设计文档 §3.3 全部 6 个 `dlc_api` 端点用 `Depends(verify_dlc_api_token)` 鉴权，但该函数**从未在文档或代码中定义**。实现者若退化为全局静态 token（例如单一 `DLC_API_TOKEN` 环境变量），会导致**运动指令下发端点无 per-device 所有权校验**。

**生产对照：** 当前 `routes/device_app_tasks.py` 每个任务端点走 `authorize(JWT)` + `require_device_control(conn, account, device_id)` 两层鉴权。新设计若使用单一共享 token，是安全降级。

**修正方案：** `/dlc/*` 端点使用 **per-device Bearer token**。生产实现不再依赖运行时可变的 `LIMA_DEVICE_TOKENS` 环境变量，而是使用数据库表持久化 token 映射；`device_gateway/auth.py` 的 `configured_device_tokens()` 仅保留为开发/应急 fallback。`verify_dlc_api_token` 校验 Bearer token 后返回其对应的 `device_id`，各端点再校验调用方是否有权操作目标设备。

**推荐表结构：**

```sql
CREATE TABLE IF NOT EXISTS v2_device_token (
  device_id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  rotated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_device_token_hash ON v2_device_token(token_hash);
```

```python
# dlc_api/auth.py — 必须显式定义
import hashlib
import secrets
from fastapi import Depends, HTTPException, Header
from device_logic.db import connect
from device_gateway.auth import configured_device_tokens  # 仅 dev fallback


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def verify_dlc_api_token(authorization: str | None = Header(default=None)) -> str:
    """校验 Bearer token，返回其对应的 device_id。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization[7:]
    token_hash = _token_hash(token)

    with connect() as conn:
        row = conn.execute(
            "SELECT device_id FROM v2_device_token WHERE token_hash=? LIMIT 1",
            (token_hash,),
        ).fetchone()
    if row is not None:
        return str(row["device_id"])

    # 开发/应急 fallback：允许从环境变量读固定 token
    for device_id, expected in configured_device_tokens().items():
        if secrets.compare_digest(token, expected):
            return device_id
    raise HTTPException(403, "invalid token")
```

#### S2 — `/dlc/tasks/dispatch` 无 per-device 所有权校验

**问题：** dispatch 是**运动指令下发**端点（控制绘图机/激光头物理运动），必须校验调用方与 `device_id` 的绑定关系。任何有效 token 者若可向**任意 device_id** 下发运动指令，等于可远程操控整个 fleet。

**修正方案：**
- 小程序路径：保留现有 `/device/v1/app/devices/{id}/tasks` 端点，继续走 `authorize(JWT)` + `require_device_control`；
- 固件/MCP 路径：`/dlc/tasks/dispatch` 使用 per-device token，`verify_dlc_api_token` 返回的 `device_id` 必须与 `body.device_id` 一致；
- `dlc_mcp` 路径：`dlc_mcp/server.py` 内部根据当前连接注册的设备选择对应 token，LLM 无法篡改 `device_id`。

修改 `dlc_api/routes.py` 中 dispatch 路由：

```python
@router.post("/dlc/tasks/dispatch")
async def dispatch_task(body: DispatchRequest, caller_device_id: str = Depends(verify_dlc_api_token)):
    # per-device 所有权校验：token 只能操作自己绑定的设备
    if caller_device_id != body.device_id:
        raise HTTPException(403, "device_id mismatch")
    # 防呆：检查设备是否已有活跃任务（§1.6.6 层 2）
    active = task_store.active_tasks_for_device(body.device_id)
    if active:
        return {"task_id": "", "status": "rejected", "reason": "device_busy",
                "active_task_id": active[0].get("task_id")}
    # ... 正常下发 ...
```

> **Ponytail 决策：** 小程序继续走现有 `/device/v1/app/devices/{id}/tasks` 端点（已有完整鉴权），`/dlc/tasks/*` 仅服务固件 + MCP 内部调用。这样零改动小程序鉴权链。

#### S7 — 固件 token 烧进镜像全设备共享

**问题：** `CONFIG_DLC_API_TOKEN` 经 menuconfig 编译进固件镜像**全设备共享同一 token**。任一设备被物理获取 → flash dump → 提取 token → 整个 fleet 远程操控权泄露。设计声称"安全配置读取"但 Kconfig string 本质是 build-time 常量。

**修正方案：**
- **每台设备独立 token**：设备首次激活时服务器下发 per-device token，存 ESP32 NVS（flash 加密 + secure boot 绑定分区）
- 服务器侧 hash 存储 token（`device_gateway/auth.py` 已有 `configured_device_tokens` per-device 模式）
- NVS 分区做 flash 加密 + secure boot 绑定

```cpp
// 修正 PostDlcApi — token 从 NVS 读取而非 Kconfig
std::string DlcMotorControlP1AiBoard::GetDlcApiToken() {
    char token[128] = {0};
    size_t len = sizeof(token);
    nvs_handle_t handle;
    if (nvs_open("dlc", NVS_READONLY, &handle) == ESP_OK) {
        nvs_get_str(handle, "api_token", token, &len);
        nvs_close(handle);
    }
    return std::string(token);
}
```

#### S9 — `0.0.0.0:8080` 监听致 TLS 后明文 token 泄露

**问题：** TLS 在 nginx 终止，`dlc_api` 监听 `0.0.0.0:8080`。若 VPS 防火墙未拒绝 8080 公网入站，攻击者绕过 nginx 直连 8080 明文 HTTP 截获 Bearer token。

**修正方案：**

```python
# server_dlc.py — 仅 bind 127.0.0.1
uvicorn.run(app, host="127.0.0.1", port=8080)  # 不是 0.0.0.0
```

```bash
# VPS iptables 拒绝 8080 公网
iptables -A INPUT -p tcp --dport 8080 -s ! 127.0.0.1 -j DROP
```

#### S12 — 小程序路径安全降级

**问题：** 设计让小程序直接调 `/dlc/tasks/dispatch`（共享 token），替代现有 `/device/v1/app/devices/{id}/tasks`（JWT + per-device ownership）。安全降级。

**修正方案（Ponytail 最小变更）：** 小程序**不改动**现有 API 调用路径，继续走 `/device/v1/app/*` 端点。`dlc_api` 的 `/dlc/tasks/*` 仅服务固件 + MCP 内部调用，不暴露给小程序。

#### SEC-04 — `dlc.draw_from_image` image_url SSRF ✅ 已修复（2026-07-06）

> **状态**：已实现。`dlc_api/routes.py::_validate_image_url` 三层防护：①字面量私网 IP 拒绝 ②`ALLOWED_IMAGE_HOSTS={"api.telegram.org"}` 主机白名单 ③`_resolve_hostname` DNS 解析后私网 IP 拒绝（防 DNS rebinding）。测试：`tests/test_sec04_ssrf_hardening.py`。

**问题：** `handle_draw_from_image(image_url)` 接收任意 HTTPS URL 并发起服务端下载做矢量化。攻击者可注入内网 URL（`169.254.169.254` 云元数据、`127.0.0.1:6379` Redis）做 SSRF 探针。

**修正方案：**

```python
# dlc_core/draw.py — image_url 域名白名单 + 私网拒绝
import ipaddress, urllib.parse

ALLOWED_IMAGE_HOSTS = {"api.telegram.org"}  # 图库下载 URL

def _validate_image_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("image_url must be https")
    if parsed.hostname not in ALLOWED_IMAGE_HOSTS:
        raise ValueError(f"image_url host not allowed: {parsed.hostname}")
    # 解析 DNS 后拒绝私网 IP
    import socket
    for addr in socket.getaddrinfo(parsed.hostname, None):
        ip = ipaddress.ip_address(addr[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("image_url resolves to private IP")
```

#### SEC-06 — Redis 任务队列投毒 ✅ 已修复（2026-07-06）

> **状态**：`device_gateway/redis_store_helpers.py::validate_task_schema` 已实现（capability 白名单 + `task_id`/`device_id` 必填校验），`RedisDeviceTaskStore.pop_pending_tasks` 在弹出时对每个任务过滤——不合格任务从 processing 队列 `lrem` 删除并 `logger.warning`，永不下发固件。测试：`tests/test_sec06_redis_schema_gate.py`（8 用例）。**待办**：Redis `requirepass`/ACL 为部署前置（运维层）。 ✅ 已修复（2026-07-06）

> **状态**：已实现。`device_gateway/redis_store_helpers.py::validate_task_schema` + `_ALLOWED_TASK_CAPABILITIES` 允许集；`RedisDeviceTaskStore.pop_pending_tasks` 在 pop 后逐条 gate，拒绝的任务从 processing 队列 `lrem` 移除并 `logger.warning`，绝不转发固件。测试：`tests/test_sec06_redis_schema_gate.py`。

**问题：** 设计文档未提及 Redis `requirepass`/ACL 配置。若 Redis 无密码，攻击者直接 RPUSH 恶意 JSON 到 pending 队列 → `pop_pending_tasks` 透传 → 固件执行恶意运动指令。`enqueue`/`pop` 不做 task schema 校验。

**修正方案：**

```ini
# Redis 配置（部署前置）
requirepass <strong-password>
# 或使用 ACL
user dlc on ><strong-password> ~lima:* +@read +@write -@dangerous
```

```python
# device_gateway/redis_store.py — pop 后加 schema gate
_ALLOWED_CAPABILITIES = {"write_text", "draw_generated", "draw_from_image", "home", "move_abs", "move_rel", "run_path"}

def _validate_task_schema(task: dict) -> bool:
    cap = task.get("capability")
    if cap not in _ALLOWED_CAPABILITIES:
        return False
    if not task.get("device_id") or not task.get("task_id"):
        return False
    return True
```

### 13.2 🟠 中等漏洞（7 项，P1-P2 修复）

| 编号 | 问题 | 修正 |
|------|------|------|
| S3 ✅ | `/dlc/tasks/preview` 无速率限制，`draw_from_image` 高 CPU/费用 DoS | 已修复：preview/dispatch 复用 `routes.rate_limit_helper.check_key_limit`（per-device key）；`draw_from_image` 走 `DEVICE.dlc_image_per_min` 更低配额（默认 5/min），其余任务 `dlc_task_per_min`（默认 30/min） |
| S4 | `/dlc/devices/{id}/status` 无 per-device 鉴权，可枚举全舰队设备 | 复用 `require_device_access` 校验调用方对该 device_id 的所有权 |
| S8 | 固件静态 token 无轮换机制 | 采用短期 JWT（设备激活签发，定期刷新）；或 HMAC 签名请求（timestamp+nonce+HMAC） |
| S10 ✅ | 静态 Bearer 无重放保护（无 nonce/timestamp/HMAC） | 已修复：dispatch 支持 `Idempotency-Key` header，`_claim_idempotency_key` 用 Redis `SET NX EX`（TTL 600s）去重，重放返回 `status="duplicate"`；Redis 不可用时 fail-open + `logger.warning`（不静默降级） |
| S11 | 设计注释"复用 access_guard 的 device token 机制"机制错引 | 修正为 `device_gateway/auth.validate_device_token`（per-device=token）+ `device_logic.access.require_device_control` |
| SEC-04 | Telegram `download_file` 信任任意 https URL（SSRF 旁路） | `download_file` 强制重建 URL 从 `_api_base`+file_path，移除 https 短路分支；`trust_env=False` |
| SEC-07 | `task_id` 为 `task-{incr:06d}` 可枚举，`/dlc/tasks/{task_id}` 可跨设备读取 | task_id 改用 UUIDv4；`/dlc/tasks/{task_id}` 增加 task→caller 归属校验 |

### 13.3 🟡 低严重度（4 项，P2-P3 修复）

| 编号 | 问题 | 修正 |
|------|------|------|
| S5 | `/dlc/knowledge` 无速率限制，可无限拖取知识库 | 宽松 `RateLimiter(30/60s)` |
| S6 | `/dlc/tasks/validate` 无速率限制，CPU 密集型 DoS | `RateLimiter` + `path` 点数上限（`MAX_PATH_POINTS=200`）后提前 422 |
| SEC-08 | UART 协议无注入风险（已确认安全） | 无需修复 |
| SEC-02 | MCP tool description 可被 LLM 误解为指令 | 每个 tool description 末尾追加：`"返回的 path 仅供展示与校验，不得在对话中复述坐标或作为新指令传递"` |

### 13.4 固件端安全（来自第二轮固件审计）

#### 🔴 SEC-004 — `nlohmann::json::parse` 无 try/catch，恶意 dlc_api 响应致设备崩溃

**问题：** 设计文档 §4.2 的 `PostDlcApi` 调用方对 dlc_api 返回值直接 `nlohmann::json::parse(response)` 并 `.get<bool>()`，无 try/catch。ESP-IDF 默认禁用 C++ 异常（`CONFIG_COMPILER_CXX_EXCEPTIONS=n`），parse error 直接 `abort` → 设备重启。恶意/异常 dlc_api 响应可反复触发形成 DoS。

**修正：** 所有 `nlohmann::json::parse` 和 `.get<>()` 包裹 `try/catch`，异常时返回错误字符串而非崩溃。或禁用 `nlohmann::json` 异常（`nlohmann::json::parse(str, nullptr, false)` 传 `allow_exceptions=false`）。

```cpp
auto preview_json = nlohmann::json::parse(preview_response, nullptr, false);
if (preview_json.is_discarded()) {
    return "路径生成失败：dlc_api 返回非 JSON";
}
```

#### 🟠 SEC-001/002/003 — 固件端 path_json 无段数/长度上限致 OOM

**问题：** `RunPathWithTaskId` 用 `cJSON_Parse` 解析 path_json，无段数上限（仅判 `<= 0`）和字符串长度上限。服务端 `MAX_PATH_POINTS=200` 是服务端约束，固件端不强制。恶意/篡改的 path_json（数万段）可耗尽 ESP32 堆内存。

**修正：**

```cpp
// motion_executor.cc — RunPathWithTaskId 入口
constexpr int kMaxPathSegments = 200;
constexpr size_t kMaxPathJsonSize = 32 * 1024;  // 32 KB

if (path_json.size() > kMaxPathJsonSize) {
    return std::string("path json too large");
}
cJSON* root = cJSON_Parse(path_json.c_str());
int total_segments = cJSON_GetArraySize(root);
if (total_segments > kMaxPathSegments) {
    cJSON_Delete(root);
    return std::string("path exceeds max segments");
}
```

同样在 `HandleMotionTaskJson` 的 path 数组分支加 `cJSON_GetArraySize(parr) > 200` 校验。

#### 🟠 SEC-005 — `http->ReadAll()` 无响应体大小限制

**修正：** ReadAll 后检查 `response.size() > 128 * 1024` 则截断返回空。

#### 🟠 SEC-006 — HTTPS 证书校验状态无法确认

**问题：** `Board::GetInstance().GetNetwork()->CreateHttp()` 来自托管组件，证书校验行为无法确认。若跳过校验，MITM 可篡改 dlc_api 响应注入恶意路径并截获 token。

**修正：**
- `sdkconfig.defaults` 显式 `CONFIG_MBEDTLS_CERTIFICATE_BUNDLE=y`
- 确认 Http 组件使用 `esp_tls` 并调用 `esp_crt_bundle_attach`
- 若不支持证书校验，改用 `esp_http_client` + `esp_tls`

#### 🟠 SEC-007 — 无强制 HTTPS 机制

**问题：** `CONFIG_DLC_API_BASE_URL` menuconfig 可配 `http://`，token 明文传输。

**修正：** `PostDlcApi` 入口运行时校验：

```cpp
if (std::string(CONFIG_DLC_API_BASE_URL).rfind("https://", 0) != 0) {
    ESP_LOGE(TAG, "DLC_API_BASE_URL must be https://");
    return "";
}
```

### 13.5 防呆机制与安全设计的关系

| 层次 | 防呆（§1.6.6） | 安全审计（§13） |
|------|---------------|----------------|
| 固件端 | `motion_busy_` 拒绝运动中重入 | `path_json` 段数/长度上限 + `json::parse` 异常保护 |
| 服务端 | `active_tasks` pre-check | dispatch per-device 鉴权 + 速率限制 + schema gate |
| 传输层 | — | TLS 强制 + 证书校验 + token 不烧镜像 + 8080 bind localhost |
| 队列层 | — | Redis requirepass + schema gate + task_id UUID |
| LLM 层 | 角色 prompt 禁止重试 | tool description 声明 path 不可执行 + tool result 净化 |
| 图库层 | — | image_url 域名白名单 + 私网拒绝 + SSRF 防护 |

> 设计完整闭环：防呆保护运动安全（不撞机），安全审计保护物理安全（不被远程操控、不被 MITM、不 OOM 崩溃）。两者互补，缺一不可。

### 13.6 补充设计级遗漏（第四轮复核）

#### T1 — LLM tool 超时与 draw_from_image 异步化

**问题：** 小智云 `connection.py:1201` 默认 `tool_call_timeout = 30s`。`dlc.write_text` 和 `dlc.draw_generated` 生成路径通常 < 3s，但 `dlc.draw_from_image` 涉及图片下载 + SVG 矢量化，可能超过 30s。超时后小智云返回"哎呀，网络遇到点问题"，用户体验差。

**修正方案：**

| Tool | 预期耗时 | 策略 |
|------|---------|------|
| `dlc.write_text` | < 1s | 同步返回 |
| `dlc.draw_generated` | 1-3s（预设图形）/ 5-10s（DashScope AI 生图，仅小程序路径） | 同步返回 |
| `dlc.draw_from_image` | 5-30s（下载+矢量化） | 同步返回，但 dlc_api 内部超时 25s（留 5s 余量给 MCP WebSocket 传输）；超时返回 `{"status": "timeout", "suggestion": "图片过大或网络慢，请稍后重试"}` |

```python
# dlc_core/draw.py — handle_draw_from_image 内部超时
import asyncio

async def handle_draw_from_image(image_url: str, ...) -> dict:
    try:
        result = await asyncio.wait_for(
            _do_draw_from_image(image_url, ...),
            timeout=25.0,  # 25s，留 5s 余量
        )
        return result
    except asyncio.TimeoutError:
        return {"status": "timeout", "error": "image vectorization timed out",
                "suggestion": "图片过大或网络慢，请稍后重试"}
```

> 固件端策略一（`self.plotter.write_text` 内部调 dlc_api）不受小智云 tool_call_timeout 限制（固件 MCP tool 在设备本地执行），但也应对 `PostDlcApi` 设置 10s 超时（已在 §9 风险表中提及）。

#### T2 — Telegram 临时 URL 时效（已修正到 §3.2 handle_draw_from_image docstring）

dlc_api 收到 `draw_from_image` 请求时**立即下载图片到本地临时文件**，后续矢量化读本地文件。不依赖远程 URL 延迟读取。

```python
# dlc_core/draw.py
async def _do_draw_from_image(image_url: str, ...) -> dict:
    # 1. 立即下载图片（URL 可能在几分钟后过期）
    import tempfile, httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(resp.content)
            local_path = f.name
    try:
        # 2. 矢量化读本地文件
        return await _vectorize(local_path, ...)
    finally:
        import os; os.unlink(local_path)
```

#### T3 — 安全测试矩阵（补充到 §8）

```bash
# 无 token → 401
curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/dlc/tasks/preview -X POST -d '{"type":"write_text","text":"test"}'
# 期望: 401

# 错误 token → 403
curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer wrong" http://127.0.0.1:8080/dlc/tasks/preview -X POST -d '{"type":"write_text","text":"test"}'
# 期望: 403

# 越权 device_id → 403
curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer <valid_token>" http://127.0.0.1:8080/dlc/tasks/dispatch -X POST -d '{"device_id":"other_user_device","type":"write_text","text":"test"}'
# 期望: 403

# SSRF image_url → 422
curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer <valid_token>" http://127.0.0.1:8080/dlc/tasks/preview -X POST -d '{"type":"draw_from_image","image_url":"https://169.254.169.254/latest/meta-data/"}'
# 期望: 422

# 超大 path_json → 422
curl -sf -o /dev/null -w "%{http_code}" -H "Authorization: Bearer <valid_token>" http://127.0.0.1:8080/dlc/tasks/validate -X POST -d "{\"path\":[$(python -c 'print(",".join([{"x":0,"y":0}]*300))')]}"
# 期望: 422 (超过 MAX_PATH_POINTS=200)

# 速率限制 → 429
for i in $(seq 1 10); do curl -sf -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer <valid_token>" http://127.0.0.1:8080/dlc/tasks/preview -X POST -d '{"type":"write_text","text":"test"}'; done
# 期望: 前 5 个 200，后续 429
```

### 13.7 配置清单汇总

**服务端环境变量（`.env` 追加）：**

```ini
# 生产环境：per-device token 主存储在数据库表 v2_device_token
# 开发/应急 fallback：允许用环境变量注入少量固定 token
LIMA_DEVICE_TOKENS=device_001=<dev-token>,device_002=<dev-token>

# Redis（安全审计 S6）
REDIS_URL=redis://:<password>@127.0.0.1:6379/0

# 设备数据库（复用现有）
DEVICE_DB_PATH=.lima-data/session.db

# MCP 接入点
MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=<JWT>
DLC_API_URL=http://127.0.0.1:8080

# Telegram 图库（复用现有）
TELEGRAM_BOT_TOKEN=<existing>
```

**固件配置（`sdkconfig.defaults` 追加）：**

```ini
CONFIG_DLC_API_BASE_URL="https://chat.donglicao.com"
# token 通过 NVS 存储（安全审计 S7），不在此硬编码
# 首次激活时由服务器下发到 NVS分区
```

**VPS 部署配置：**

```bash
# /etc/systemd/system/dlc-drawing.service
[Unit]
Description=DLC Drawing Service
After=redis-server.service

[Service]
ExecStart=/usr/bin/python3 -m uvicorn dlc_api.app:app --host 127.0.0.1 --port 8080
User=dlc
EnvironmentFile=/opt/dlc-drawing/.env
Restart=always

[Install]
WantedBy=multi-user.target

# iptables 规则（安全审计 S9）
iptables -A INPUT -p tcp --dport 8080 -s ! 127.0.0.1 -j DROP
```

> `--host 127.0.0.1`（不是 `0.0.0.0`）：nginx 反代 443 → 127.0.0.1:8080，公网无法直连。

---

## 14. 设计工具链与参考来源

> 本节记录本设计文档在编写与复核过程中使用/参考的 skills、MCP servers、GitHub 仓库及官方文档，便于后续 Agent 复现设计思路、查证证据链，也作为进入实现阶段前的工具清单。

### 14.1 设计阶段使用的 Skills

按职责分类，**不限制当前是否已安装**，实现阶段建议按需加载：

| 分类 | Skill 名称 | 用途 | 建议触发时机 |
|------|-----------|------|-------------|
| LiMa 项目流程 | `lima-plan` | 非平凡改动的计划制定、影响面分析、计划文件输出 | 本设计文档制定与复核 |
| LiMa 项目流程 | `lima-test` | 一键执行 pytest、ruff、pyright、check_code_size | 提交前门禁 |
| 需求澄清 | `requirements-elicitation` | 在需求不明确时澄清目标、范围、验收标准 | 设计初期 |
| 意图分析 | `intent-driven-development` | 把模糊需求转化为可验证的验收标准 | 设计初期 |
| 系统调试 | `systematic-debugging` | 遇到 bug 或测试失败时的结构化排查 | 实现/测试阶段 |
| 嵌入式/固件 | `esp32` | ESP32 芯片、ESP-IDF、PlatformIO 硬件与固件指导 | 改 `u8-xiaozhi/main/` 前必加载 |
| 嵌入式/固件 | `esp-idf-handling` | ESP-IDF 项目 build/flash/monitor/OTA 完整生命周期 | 固件编译/烧录 |
| 嵌入式/固件 | `esp-pio-handling` | PlatformIO 构建/上传/监控 ESP32 固件 | 若用 PlatformIO 路径 |
| 嵌入式/固件 | `serial` / `jlink` / `openocd` | 串口日志、调试器、烧录 | 真机调试 |
| 嵌入式/测试 | `workbench-*`（workbench-wifi / workbench-mqtt / workbench-logging / workbench-test-handling） | Universal Embedded Workbench 上的 WiFi/MQTT/日志/测试自动化 | 硬件台架测试 |
| 后端/Python | `fastapi-patterns` | FastAPI + Pydantic v2 + 依赖注入 + 测试最佳实践 | 写 `dlc_api` 时 |
| 后端/Python | `python-patterns` | Pythonic  idioms、类型提示、代码规范 | 写 Python 模块时 |
| 后端/Python | `python-testing` | pytest、TDD、fixtures、mocking、覆盖率 | 写测试时 |
| 后端/Python | `tdd-workflow` | 80%+ 覆盖率的 TDD 流程 | 新功能/bugfix |
| 后端/安全 | `security-review` | 认证、输入验证、secret、支付/敏感特性检查清单 | 涉及安全边界时 |
| 前端/小程序 | `vue-patterns` | Vue 3 Composition API、Pinia、Vue Router、Nuxt SSR | 改 manager-mobile 时 |
| MCP | `mcp-server-patterns` | 用 Node/TypeScript SDK 或 Python MCP SDK 构建 MCP server | 写 `dlc_mcp/server.py` 时 |
| 通用设计 | `design-taste-frontend` / `minimalist-ui` | 若需要重塑小程序 UI 时使用 | UI 重设计 |

### 14.2 设计阶段使用的 MCP Servers

| MCP Server | 来源 | 本设计中的用途 |
|------------|------|---------------|
| `codegraph` | 本地二进制（`.codegraph/codegraph.db`）| 调用图、影响分析、死代码审计；复核前执行 `codegraph sync .` |
| `fetch` | `uvx mcp-server-fetch` | 抓取网页内容（微信官方文档、GitHub README、Telegram Bot API 等） |
| `filesystem-qwen` | 本地 npm 包 | 访问 `D:/QWEN3.0` 项目文件 |
| `filesystem` | 本地 npm 包 | 访问 `C:/Users/zhugu` 用户级配置 |
| `git` | 本地 npm 包 | 当前仓库 Git 操作（本设计阶段主要用 `git status`/`git diff` 确认变更范围） |
| `context7` | 本地 npm 包 | 框架/库文档知识库检索（FastAPI、Vue、ESP-IDF 等） |
| `sqlite` | 本地 npm 包 | 访问 `D:/QWEN3.0/.lima-data/session.db`（设备/任务 schema 复核） |
| `github` | 本地 npm 包 | GitHub issue/PR/仓库操作（设计阶段未实际修改远程，实现阶段用于 PR） |
| `chrome-devtools` | 本地插件 | 浏览器自动化（本设计阶段未使用；后续若做小程序 H5 页面或 Web 管理端测试时使用） |

### 14.3 参考的 GitHub 仓库

| 仓库 | 用途 | 本设计中引用的证据 |
|------|------|------------------|
| `78/esp-wifi-connect` | ESP32 Wi-Fi 连接组件，提供 SoftAP HTTP 配网 | §4.3/§5.2.6：SSID 生成规则 `{prefix}-{mac[4]:02X}{mac[5]:02X}`、`WIFI_AUTH_OPEN`、 `/submit` 仅解析 ssid/password、`/exit` 端点 |
| `xinnan-tech/xiaozhi-esp32-server` | 小智官方自托管服务器 | §2.3：链式 tool call 证据 `MAX_DEPTH=5` + `_handle_function_result()` + `chat(depth+1)` |
| `xinnan-tech/mcp-endpoint-server` | 自托管 MCP endpoint server（模式 B） | §6.2：配置文件 `data/.mcp-endpoint-server.cfg`、连接方向、部署步骤 |
| `78/mcp-calculator` | MCP WebSocket 桥接示例 | §6.2：参考 `mcp_pipe.py` 把 stdio MCP server 桥接到 WebSocket |
| `DietrichGebert/ponytail` | Ponytail「lazy senior dev」原则 | §1.4：第一开发原则，能少写就少写、优先复用 GitHub 高可靠实现 |
| `tdlib/td` | Telegram 客户端库 | §1.6.1：Telegram Bot API 速率限制证据（同会话 1 msg/s，全局 30 msg/s） |
| `mac8005/xiaozhi-mcp-ha` / `shawn996/mcp_ha_xiaozhi` | 第三方小智 MCP Home Assistant 桥接 | §6.1：佐证 `wss://api.xiaozhi.me/mcp/?token=...` 为官方云原生 MCP endpoint |
| 本项目 LiMa（`D:/QWEN3.0`） | 自身代码库 | 全部现有代码路径引用（`device_gateway/`、`routing_engine/`、`session_memory/` 等） |

### 14.4 官方文档参考

| 文档 | 用途 | 本设计中引用的证据 |
|------|------|------------------|
| [微信官方文档 - wx.connectWifi](https://developers.weixin.qq.com/miniprogram/dev/api/device/wifi/wx.connectWifi.html) | 小程序自动连 WiFi | §4.3/§5.2.6：Android 10+ 需 `maunal:true`、iOS 需监听 `onWifiConnected`、open 网络传空密码 |
| [微信官方文档 - wx.writeBLECharacteristicValue](https://developers.weixin.qq.com/miniprogram/dev/api/device/bluetooth-ble/wx.writeBLECharacteristicValue.html) | 小程序蓝牙写特征值 | §5.2.6：单次写入建议不超过 20 字节，并行写易失败，iOS 长数据无回调 |
| [Telegram Bot API](https://core.telegram.org/bots/api#handling-errors) | Telegram Bot 限制 | §1.6.1：速率限制证据 |
| 小智官方文档（本地缓存：`docs/xiaozhi-cloud/`；线上 `https://xiaozhi.dev/docs/` / `https://xiaozhi.me`）| 小智云能力、控制台、MCP 接入 | §1.3、§6.1、§6.2：官方云 endpoint、控制台路径、角色 prompt 配置 |

### 14.5 使用建议

1. **进入实现阶段前**，Agent 应优先加载 `lima-plan` → `esp32` / `fastapi-patterns` / `vue-patterns` / `mcp-server-patterns` / `security-review` 等对应领域 skill。
2. **大规模重构/删除前**，先执行 `codegraph sync .` 并做 `codegraph impact <symbol>` 影响分析。
3. **引用外部仓库时**，优先使用 `fetch` MCP 抓取最新源码或官方文档，避免依赖训练数据中的过期信息。
4. **P0 实测项**（小智云 LLM 链式调用行为）需用真实 `xiaozhi.me` 账号验证，无法仅通过文档/源码得出结论。