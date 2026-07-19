# C1 Workflow 持久化立项设计

## 背景与问题

LiMa 的设备任务状态机（`device_workflow/orchestrator.py`）当前是纯内存的 `WorkflowOrchestrator` 单例。`device_ledger` 虽然已实现 Redis 后端（`device_ledger/redis_store.py`），但 `server_dlc.py` 的 lifespan 没有调用 `configure_ledger_store_from_env()`，生产默认仍用内存。结果是：

- 进程重启后，所有在途任务（planned/simulated/waiting_approval/dispatched/running 等）的状态丢失。
- 已实现的 `RedisDeviceTaskStore` 只持久化任务队列/快照，不持久化 `WorkflowOrchestrator` 的精细状态与历史。
- `v2_task` SQLite 表保存了小程序任务审批/运行/终态快照，但与内存状态机是两条线。

C1 的目标是为这套 workflow 设计一套可跨进程恢复、 eventually-consistent 的持久化方案，而不是直接写代码。

## 范围

**在范围内：**
- `device_workflow/orchestrator.py` 的状态与历史持久化/恢复。
- `device_ledger` 在生产环境默认启用 Redis 后端（ lifespan 补配置）。
- `device_gateway/task_store` 与 workflow 状态之间的映射与一致性。
- 进程重启后“未终态任务”的恢复策略（重放 ledger 事件 vs 快照）。
- 多 worker/多节点下的并发写约束（Redis Lua CAS 复用）。

**不在范围内（本次立项）：**
- 新增 HTTP admin 路由或 UI。
- 替换 Redis 为 Postgres/其他后端。
- 设备 WebSocket 会话（`device_gateway/sessions.py`）持久化：WS 天然需要重连，本次不持久化 socket 句柄。
- `device_memory` / `device_intelligence/shadow.py` 的全状态持久化：这些已有 Redis 后端，但缺少 lifespan 配置，本设计只给出启用建议，不单独做 schema。

## 候选方案

### 方案 A：事件源为唯一真相源（推荐）

以 `device_ledger` 的 append-only 事件流为唯一真相源；`WorkflowOrchestrator` 变为事件流的投影（projection）。

- 所有状态推进必须通过一个 `WorkflowEvent` 写入 ledger（`device_ledger/store.py`）。
- `WorkflowOrchestrator` 不再自己维护 `_states/_history/_timestamps`；调用 `get_state(task_id)` 时重放该任务的 ledger 事件（或读本地缓存）。
- 启动恢复：服务启动时无需全量加载，首次访问任务时 lazy replay；也可以预热未终态任务集合。
- `task_store` 继续保存任务队列/快照，作为执行侧视图；ledger 保存状态机真相源。

**优点：**
- 状态机与历史天然一致，重启后可通过事件重放恢复。
- 与已有 `device_ledger/projection.py` 对齐。
- 多 worker 共享 Redis ledger 即可实现状态共享。

**缺点：**
- 每个 `get_state` 都重放事件有性能开销；需要引入快照/缓存。
- 需要把现有所有 `workflow.advance()` 调用点改为先写 ledger 再更新投影。

### 方案 B：双写状态快照

保留内存状态机，但每条状态变更同时写入 Redis/SQLite 快照表；启动时从快照加载未终态任务。

- `WorkflowOrchestrator` 内部新增 `PersistedWorkflowStore` 后端接口。
- 每次 `register`/`advance` 后把 `(task_id, state, history, timestamps)` 写入后端。
- 启动时扫描所有非终态快照并加载回内存。

**优点：**
- 对现有调用链改动小，读状态仍走内存。
- 实现快，短期可见效果。

**缺点：**
- 双写容易不一致（内存写成功、持久化失败时状态丢失或漂移）。
- 多 worker 同时 advance 同一任务时，需要分布式锁，实现复杂且容易出错。
- 历史与快照可能不一致，调试困难。

## 推荐方案：A（事件源 + 快照缓存）

理由：项目已有 ledger 事件流和 projection 基础设施，且事件源是持久化状态机最干净的方式。方案 B 的“双写”本质上是重复实现一套持久化，长期债务更重。

## 关键设计决策

### 1. 事件类型扩展

`device_ledger/events.py` 已有 `LedgerEvent`。新增/复用事件类型映射 `WorkflowEvent`：

| WorkflowEvent | LedgerEvent |
|---------------|-------------|
| PLAN_READY | task_created / task_updated (status=planned) |
| SIM_READY | task_updated (status=simulated) |
| REQUIRES_APPROVAL | task_updated (status=waiting_approval) |
| AUTO_APPROVE / APPROVED | task_updated (status=ready_to_dispatch) |
| REJECTED | task_terminal (phase=rejected) |
| DISPATCH | task_dispatched |
| START | task_acknowledged |
| COMPLETE | task_terminal (phase=done) |
| FAIL | task_terminal (phase=failed) |
| CANCEL | task_terminal (phase=cancelled) |
| ERROR | task_terminal (phase=error) 或 task_updated |
| RECOVERED | task_progress / motion_event |

需要新增 `task_updated` 事件类型或复用 `motion_event`；建议新增 `task_updated`，payload 包含 `{state: "waiting_approval", reason: "..."}`，便于 projection 直接映射到 `TaskState`。

### 2. WorkflowOrchestrator 改造

`device_workflow/orchestrator.py`：

- 保留线程锁，但内部不再维护 `_states/_history/_timestamps` 作为真相源。
- `register(task_id)` → 写 `task_created` 事件。
- `advance(task_id, target)` → 先校验当前状态（通过投影），然后写对应 `task_updated`/`task_dispatched`/`task_acknowledged`/`task_terminal` 事件；成功后返回投影状态。
- `get_state(task_id)` → 调用 `task_projection.rebuild_state(task_id)`，再映射到 `TaskState`。
- `history(task_id)` → 直接重放 ledger 事件并返回 `TaskState` 列表。
- `snapshot(task_id)` → 返回投影结果。

为减少重复重放，可在 orchestrator 内加短期本地缓存（TTL 5s，版本号/事件数校验），但缓存不是持久化的一部分。

### 3. 启动恢复策略

`server_dlc.py` lifespan：

1. 调用 `configure_task_store_from_env()`（已有）。
2. 新增调用 `configure_ledger_store_from_env()`；如果 Redis URL 不存在则保留内存并告警。
3. 启动后扫描 `task_store` 中所有非终态任务（`status not in {completed, failed, cancelled, terminal}`），对每个任务调用 `workflow.get_state(task_id)` 做一次 lazy replay/校验，把不一致状态记录到日志。

不需要在启动时全量重建所有任务；首次访问时 replay 即可。

### 4. 并发控制

- 状态机推进改为“写 ledger 事件”后，利用 `RedisLedgerStore` 的 append 原子性（Redis list LPUSH / stream XADD）保证事件追加有序。
- 同一任务的并发 advance：在 orchestrator 内使用 per-task `threading.RLock` 或 Redis 分布式锁（Redlock）防止双写；第一阶段可用线程锁 + 单 worker 部署，第二阶段加 Redis 锁支持多节点。
- `task_store` 继续用现有 Lua CAS 处理队列侧并发。

### 5. task_store 与 ledger 的边界

- `task_store` 负责“任务能不能被设备拉走、当前在队列中的位置、重试次数”等执行侧状态。
- `ledger` / `workflow` 负责“业务生命周期状态机 + 审计历史”。
- 两者通过 `task_id` 关联；恢复时以 ledger 为准，task_store 作为执行侧视图可重新入队。

### 6. 状态映射一致性

定义 `TaskState` ↔ `task_store.status` 显式映射表，写入 `device_workflow/state.py` 注释或新增 `STATE_TO_STORE_STATUS`：

```text
CREATED/PLANNED/SIMULATED/WAITING_APPROVAL/READY_TO_DISPATCH → "created"/"queued"/"pending"
DISPATCHED → "dispatching"
RUNNING/IN_PROGRESS/RECOVERING → "running"
TERMINAL/COMPLETED → "completed"
FAILED → "failed"
CANCELLED → "cancelled"
```

`routes/device_app_task_store.py` 在审批/推进 workflow 时，同时更新 `v2_task.status` 为对应映射值。

### 7. TTL 与清理

- Redis ledger 事件使用 `redis_ledger_ttl`（已存在配置）过期；终态任务的事件可保留 7 天用于审计。
- `v2_task` 表作为长期可查询快照保留，定期归档（独立运维脚本，不在 C1 实现）。

## 里程碑 / 实施切片

**Phase 0：立项与门禁（本计划）**
- 输出 `docs/plans/c1-workflow-persistence-design.md`。
- 评审通过后再写代码。

**Phase 1：Ledger 生产启用**
- `server_dlc.py` lifespan 调用 `configure_ledger_store_from_env()`。
- 新增环境变量 `LIMA_DEVICE_LEDGER_STORE` 到 `.env.example`。
- 补充测试：Redis backend 启动后 ledger 事件可跨进程读取。

**Phase 2：WorkflowOrchestrator 事件源化**
- 修改 `device_workflow/orchestrator.py`：所有方法改为写/读 ledger 事件。
- 新增 `task_updated` ledger 事件类型。
- 更新 `device_ledger/projection.py` 支持 `task_updated` 到 `TaskState` 的映射。
- 保持现有 `workflow.advance(...)` 调用点不变（内部实现变）。

**Phase 3：启动恢复与一致性校验**
- lifespan 启动时扫描非终态任务并 lazy replay。
- 新增测试：模拟进程重启后，任务状态可从 ledger 恢复。

**Phase 4：并发与多 worker（可选）**
- 为 `WorkflowOrchestrator.advance()` 增加 per-task 锁（线程锁或 Redis 分布式锁）。
- 压力测试：多 worker 同时推进同一任务只产生合法事件序列。

**Phase 5：集成与部署**
- 更新 `deploy_unified.py` 环境模板，确保生产 Redis URL 配置。
- 在 staging 做重启恢复演练。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 事件源改造引入状态机回退不一致 | 所有状态推进先读当前投影再写事件；非法 transition 在写事件前拒绝。 |
| Redis ledger 不可用导致服务无法启动 | lifespan 中捕获异常并允许内存回退，但日志告警；生产应配置 Redis。 |
| 启动时扫描大量非终态任务阻塞 lifespan | 改为后台任务 lazy replay，lifespan 只触发异步扫描。 |
| 现有 `v2_task` 状态与 ledger 状态 divergence | 新增一致性校验日志；以 ledger 为准，逐步收敛。 |
| 多 worker 并发推进同一任务 | Phase 4 加 per-task 锁；Phase 1/2 默认单 worker 跑。 |

## 验收标准

1. `server_dlc.py` lifespan 启用 ledger Redis 后端（配置存在时）。
2. `WorkflowOrchestrator` 的所有状态推进均通过 ledger 事件实现；内存单测中重启（替换 ledger_store 为新的 Redis 实例）后可重放状态。
3. `pytest tests/test_device_workflow.py tests/test_device_ledger.py` 新增/更新用例通过；全量 pytest 通过。
4. 部署文档更新：`.env.example` 与 `docs/DEPLOY_AND_RELEASE_CONVENTION.md` 说明 `LIMA_DEVICE_LEDGER_STORE`。
5. 不提供 UI；API 行为不变（状态查询接口返回的状态与当前一致）。
