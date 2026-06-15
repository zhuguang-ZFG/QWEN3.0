# LiMa 代码质量治理执行计划（2026-06-15）

**状态**: Q0–Q4 已关闭（2026-06-15）；Q5–Q7 待执行
**Owner**: zhuguang-ZFG
**权威级别**: 本文件为代码质量治理的**唯一执行清单**；Agent/协作者须按切片顺序执行，不得跳步或擅自改范围。

**关联文档**:

- [`PROJECT_OPTIMIZATION_ROADMAP_CN.md`](../../PROJECT_OPTIMIZATION_ROADMAP_CN.md) — 设备战略路线图（并行，不冲突）
- [`STATUS.md`](../../../STATUS.md) — 当前状态快照
- [`AGENTS.md`](../../../AGENTS.md) — 硬规则（无静默降级、≤300 行/文件等）

---

## 一、背景与基线（2026-06-15）

### 1.1 质量现状摘要

| 维度 | 状态 |
|------|------|
| P0 违规 | 已修复（STATUS 2026-06-15） |
| Legacy 路由栈 | 已退役 |
| ruff | clean |
| 测试 | 2009+；设备聚焦 452 passed |
| 超标生产文件（>300 行） | 约 32 个（不含 tests） |
| `repo_stats.py` 行数 | **失真**（含 `.venv310` site-packages） |

### 1.2 实际源码规模（排除 `.venv*`、`esp32S_XYZ`）

```
python_files  ≈ 1,076
python_lines  ≈ 147,000
```

### 1.3 执行原则

1. **文档先行**：契约类改动（Q1）须先有 `docs/superpowers/specs/` 短设计。
2. **切片 closeout**：每切片完成 → 聚焦 pytest → ruff → `progress.md` / `findings.md` 证据。
3. **不改行为除非 spec 写明**：拆分（Q2）仅移动代码，API 不变。
4. **仅 stage 本轮文件**；commit/push/deploy 须 Owner 明示。
5. **晋升规则**：切片 checkbox 全绿 + 验证命令输出记录在 `progress.md`。

---

## 二、切片总览与依赖

```text
Q0 统计/CI 基线 ──┬──> Q1 route_policy 统一 ──> Q2 tasks 拆分 ──> Q4 Store 生产化
                  ├──> Q3 routing_executor
                  ├──> Q6 测试卫生
                  └──> Q5 次级拆分（排队）

Q4 完成后 ──> Q7 战略瘦身评估（仅规划）
```

| 切片 | 名称 | 预估 | 状态 |
|------|------|------|------|
| Q0 | 统计与 CI 基线修正 | 0.5d | ✅ 已关闭 |
| Q1 | route_policy 单一真相源 | 1d | ✅ 已关闭 |
| Q2 | 拆分 `device_gateway/tasks.py` | 1–2d | ✅ 已关闭 |
| Q3 | `routing_executor` 显式依赖 | 0.5d | ✅ 已关闭 |
| Q4 | Store 生产化（memory + ledger） | 2–3d | ✅ 已关闭 |
| Q5 | 次级超标文件拆分 | 按文件排队 | ⬜ 待执行 |
| Q6 | 测试卫生 | 并行 | ⬜ 待执行 |
| Q7 | 战略瘦身评估 | 规划 only | ⬜ 待执行 |

---

## 三、Q0 — 统计与 CI 基线修正

**目标**：修正失真统计；恢复 P1.3 CI 门；对齐记忆文档。

| ID | 任务 | 文件 | 完成 |
|----|------|------|------|
| Q0-1 | `SKIP_PARTS` 加入 `.venv`、`.venv310` 及通配 `.venv*` 前缀目录 | `scripts/repo_stats.py` | ✅ |
| Q0-2 | 刷新仓库规模表（运行 `python scripts/repo_stats.py` 填数） | `CLAUDE.md` | ✅ |
| Q0-3 | 重写 `test_p13_no_silent_exception_pass_in_active_paths` | `tests/test_ci_gates.py` | ✅ |
| Q0-4 | P1.3 标 **Closed**，指向 STATUS + 本计划 | `docs/LIMA_MEMORY_CN.md` | ✅ |

**验证**:

```powershell
python scripts/repo_stats.py
python -m pytest tests/test_ci_gates.py::test_p13_no_silent_exception_pass_in_active_paths -v
ruff check scripts/repo_stats.py tests/test_ci_gates.py
```

**晋升**: `python_lines` < 200,000；P13 测试不 skip 且通过。

---

## 四、Q1 — route_policy 单一真相源

**目标**：`esp32s_adapter` 与 `device_gateway.model_routing` 语义一致（`run_path` → `device_vector`）。

| ID | 任务 | 完成 |
|----|------|------|
| Q1-0 | 写 spec | `docs/superpowers/specs/2026-06-15-esp32s-adapter-route-policy-unify.md` | ✅ |
| Q1-1 | `generate_route_policy(cap)` 委托 `resolve_device_route_policy` | `esp32s_adapter/protocol.py` | ✅ |
| Q1-2 | 删除本地 `CONTROL_CAPABILITIES` 副本 | 同上 | ✅ |
| Q1-3 | 测试期望：`run_path` → `device_vector` | `tests/test_esp32s_adapter_protocol.py` | ✅ |

**验证**:

```powershell
python -m pytest tests/test_esp32s_adapter_protocol.py tests/test_device_gateway_model_routing.py -q
```

**晋升**: 两套件全绿；findings 记录 CQ-Q1。

---

## 五、Q2 — 拆分 `device_gateway/tasks.py`

**目标**：521 行 → facade ≤80 行 + 3 子模块各 ≤220 行；**对外 import 路径不变**。

| 新模块 | 职责 | 迁入符号 |
|--------|------|----------|
| `task_creation.py` | 任务创建与投影 | `project_to_motion_task`, `_create_task_from_voice_task`, `create_task_from_transcript`, `_looks_like_svg_path` |
| `task_events.py` | 事件、恢复、memory、workflow | `record_motion_event`, `execute_recovery`, `_extract_memory_from_terminal`, `_recovery_*`, `_advance_workflow_on_event`, `_retry_task`, `_issue_home_command`, `TERMINAL_PHASES` |
| `task_lifecycle.py` | 队列与派发 | `mark_task_dispatched`, `ack_processing_task`, … | 72 行 |
| `task_deps.py` | 可 monkeypatch 依赖层 | `resolve_device_route_policy`, `validate_route_policy`, … | 新建 |
| `tasks.py` | Facade + 测试兼容 re-export | `reset_tasks_for_tests`, … | 68 行 |

| ID | 任务 | 完成 |
|----|------|------|
| Q2-1 | 创建子模块 + `task_deps` 并迁移 | ✅ |
| Q2-2 | `tasks.py` facade + re-export | ✅ |
| Q2-3 | `mark_task_dispatched` 静默 pass → `_log.debug` | ✅ |

**验证**:

```powershell
python -m pytest tests/test_device_gateway_routes.py tests/test_device_gateway_model_routing.py tests/test_device_recovery_execution.py tests/test_device_ledger_artifacts.py -q
ruff check device_gateway/
```

**晋升**: `tasks.py` ≤80 行；设备相关测试全绿。

---

## 六、Q3 — routing_executor 显式依赖

| ID | 任务 | 完成 |
|----|------|------|
| Q3-1 | 顶部 `import budget_manager`, `import health_tracker` | `routing_executor.py` | ✅ |
| Q3-2 | 删除 `import routing_engine as re` | 同上 | ✅ |
| Q3-3 | `_parallel_fallback` 移除未使用的 `re` 参数 | 同上 | ✅ |

**验证**:

```powershell
python -m pytest tests/test_routing_engine.py tests/test_routing_pipeline_authority.py -q
ruff check routing_executor.py
```

---

## 七、Q4 — Store 生产化

复制 `device_gateway/store.py` 的 `LIMA_*_STORE` env 模式（默认 `memory`；`redis` 需 `LIMA_DEVICE_REDIS_URL`）。

### Q4-A — device_memory

| ID | 任务 | 文件 | 完成 |
|----|------|------|------|
| Q4-A1 | `MemoryStoreBackend` 协议 + `InMemoryMemoryStore` | `device_memory/store.py` | ✅ |
| Q4-A2 | `RedisMemoryStore` | `device_memory/redis_store.py` | ✅ |
| Q4-A3 | `configure_memory_store_from_env()` / `get_memory_store()` | `device_memory/store.py` | ✅ |
| Q4-A4 | 启动时配置 + `/device/v1/health` 暴露 `memory_store` | `routes/device_gateway.py` | ✅ |

环境变量：`LIMA_DEVICE_MEMORY_STORE=memory|redis`

### Q4-B — device_ledger

| ID | 任务 | 文件 | 完成 |
|----|------|------|------|
| Q4-B1 | `LedgerStoreBackend` 协议 + 保留 `InMemoryLedgerStore` | `device_ledger/store.py` | ✅ |
| Q4-B2 | `RedisLedgerStore` | `device_ledger/redis_store.py` | ✅ |
| Q4-B3 | `configure_ledger_store_from_env()` | `device_ledger/store.py` | ✅ |
| Q4-B4 | 启动时配置 + health 暴露 `ledger_store` | `routes/device_gateway.py` | ✅ |

环境变量：`LIMA_DEVICE_LEDGER_STORE=memory|redis`

**验证**:

```powershell
python -m pytest tests/test_device_store_redis_backends.py tests/test_device_memory_*.py tests/test_device_ledger_artifacts.py -q
ruff check device_memory/ device_ledger/
```

**晋升**: 单进程默认行为不变；`LIMA_DEVICE_*_STORE=redis` 无 URL 时 fail-fast；Redis 假客户端集成测试通过。

---

## 八、Q5 — 次级超标文件（排队，单次只拆一个文件）

| 优先级 | 文件 | 行数 | 建议 |
|--------|------|------|------|
| P5-1 | `channel_gateway/service.py` | ~~567~~ **221** | ✅ greeting + outbound + service_dispatch 拆分 |
| P5-2 | `orchestrate.py` | ~~451~~ **122** | ✅ constants + detect + pipeline 拆分 |
| P5-3 | `routes/admin_api_extra.py` | ~~463~~ **29** | ✅ admin_extra_* 域拆分 |
| P5-4 | `eval_loop.py` | ~~612~~ **51** | ✅ 移 scripts + 数据 JSON 化（optional 离线工具） |
| P5-5 | `routing_intent.py` | ~~312~~ **247** | ✅ image/thinking → routing_intent_modal |
| P5-6 | `speculative.py` | ~~312~~ **28** | ✅ execution + policy 拆分 |

---

## 九、Q6 — 测试卫生

| ID | 任务 |
|----|------|
| Q6-1 | 拆 `tests/test_provider_automation.py` (850) | ✅ 4 文件 + helpers |
| Q6-2 | 拆 `tests/test_ops_metrics.py` (752) | ✅ 4 文件 + helpers |
| Q6-3 | `tests/README.md` 记录聚焦门 vs 全量门命令 | ✅ |

---

## 十、Q7 — 战略瘦身评估（仅文档产出）

| ID | 任务 | 状态 |
|----|------|------|
| Q7-1 | 产出 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md`（hot/warm/cold 表） | ✅ |

审计范围：`context_pipeline/`、`provider_probe/`、`provider_automation/`、`orchestrate.py`

---

## 十一、全局 Closeout 检查清单

每切片复制使用：

- [ ] 本计划对应 checkbox 已勾选
- [ ] 聚焦 pytest 通过（输出贴入 `progress.md`）
- [ ] `ruff check` 触及文件 clean
- [ ] 无新增裸 `except: pass`（P13 门覆盖）
- [ ] `progress.md` / `findings.md` 有证据行（ID: CQ-Qn-x）
- [ ] 契约改动时更新 `STATUS.md`
- [ ] 仅 stage 本轮文件

---

## 十二、执行日志（随 closeout 更新）

| 日期 | 切片 | 结果 | 证据 |
|------|------|------|------|
| 2026-06-15 | Q0 | Closed | `repo_stats`: 805 files / 98768 lines；P13 测试恢复通过 |
| 2026-06-15 | Q1 | Closed | esp32s_adapter `run_path`→`device_vector`；11 protocol tests pass |
| 2026-06-15 | Q2 | Closed | tasks.py 521→68 行；子模块 task_creation/events/lifecycle/deps |
| 2026-06-15 | Q3 | Closed | routing_executor 显式 import health_tracker/budget_manager；112 focused pass |
| 2026-06-15 | Q4 | Closed | memory/ledger env 切换 + Redis 后端；63 tests passed；health 暴露 store 后端 |
| 2026-06-15 | Q5-1 | Closed | service.py 567→221 行；greeting/outbound/service_dispatch；41 channel tests pass |
| 2026-06-15 | Q5-2 | Closed | orchestrate.py 451→122 facade；constants/detect/pipeline；1 test + __main__ pass |
| 2026-06-15 | Q5-3 | Closed | admin_api_extra 463→29 facade；8 个 admin_extra_* 子模块；11 admin tests pass |
| 2026-06-15 | Q5-4 | Closed | eval_loop 移 scripts/；根目录 51 行 shim；default_eval_set.json；自测通过 |
| 2026-06-15 | Q5-5 | Closed | routing_intent 312→247；routing_intent_modal 77 行；13 intent tests pass |
| 2026-06-15 | Q5-6 | Closed | speculative 312→28 facade；execution(219)+policy(145)；telemetry test pass |
| 2026-06-15 | Q6 | Closed | provider_automation 850→4 文件；ops_metrics 752→4 文件；tests/README 聚焦/全量门；83 pass |
| 2026-06-15 | Q7 | Closed | `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` hot/warm/cold 评估；docs/README 已索引 |
