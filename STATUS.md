# LiMa Status

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com, api.donglicao.com
> **部署**: Alibaba Cloud VPS + JDCloud 备用

> Updated: 2026-06-15
> Branch: `design/route-policy-backend-field`
> Tests: **2009+ tests** (452 in focused device suite); ruff clean; pre-commit passing
> Quality: P0 violations resolved; legacy routing/HTTP stack retired

## 当前项目状态

### 核心功能
- **设备网关**: ESP32 绘图机/写字机云端控制
- **AI 路由**: 170+ 后端智能路由（设备任务 + 聊天/编码）
- **任务管理**: 任务创建、派发、执行、监控
- **设备策略**: 安全策略、固件兼容性、路径验证

### 最近完成（2026-06-15）Hardware AI Phase 1 M5–M8 Closeout

- **M5 Recovery + Reliability**：`execute_recovery()` 实现 retry/home/stop 决策；重试耗尽后 action 改为 `"stop"`；retry 任务 WS 直发时从 pending queue 移除，避免双发；task store 增加 `increment_retry_count` / `reset_task_for_retry` / `remove_pending_task`；`RedisDeviceTaskStore` 补齐相同协议
- **M6 Memory + Continuous Learning**：新增 `device_memory/extractor.py` / `consolidation.py` / `recall.py` / `quality_gates.py` / `store.py` / `routes/device_memory.py`；terminal 事件自动提取 episode 与 failure pattern；episode ID 加入 `event_id` 防止重试历史覆盖；memory 提取失败改为 `logger.warning`（符合 AGENTS.md 无静默降级）；`MemoryStore` 加 RLock 并标注生产化 TODO
- **M7 External Enrichment + Support/Ops**：`device_support/snapshot.py` 提供 shadow/firmware/self-check/近期终端任务/故障告警/脱敏建议；support snapshot 过滤 24h 时间窗口；`external_enrichment` 天气/节假日 provider 验证可用
- **M8 OTA + Release Gate**：`device_ota/release.py` + `canary.py` + `routes/device_ota.py`；新增 `/deploy/{version}`、`/canary/record-success/{device_id}`、`/canary/record-failure/{device_id}`、`DELETE /canary/devices/{device_id}`；未知 criteria 返回 400；gate 未就绪时 deploy 返回 412；部署新版本自动重置 canary 计数
- **代码审查修复**：review 发现的 6 个 P0/P1 问题全部修复，新增 20+ 测试覆盖去重、Redis store 协议、OTA 路由、support 时间窗口
- **测试**：device 聚焦套件 452 passed；ruff clean

- **死区代码清理**：删除 `routes/ops_probe_ingest.py`、`converters/anthropic_format.py`、`deploy/key_rotation.py`、`scripts/vps_eval_smoke_remote.py` 等 4 个死文件
- **Anthropic 残留清理**：移除 `/v1/messages` 端点及所有 Anthropic 转换函数（chat_endpoints.py 363→142 行）；route_registry.py 移除 4 个 anthropic 字段 + 7 个 agent_* 硬编码 False
- **配置死路径清理**：pyrightconfig.json 移除 agent_runtime/voice_gateway/code_orchestrator_context 等 8 个不存在的 include/exclude 路径；ruff.toml 移除 8 个不存在 exclude 路径；deploy_unified.py 移除 agent_runtime core dir + m1m5 slice + eval smoke 代码
- **文档清理**：归档 task_plan.md、OPS_ENTRYPOINTS_CN.md、FREE_MODEL_ROUTING_STATUS_CN.md、MODEL_CATALOG.md、ROUTING_ENGINE_DESIGN.md、PLAN_CLOSURE_STATUS.md 至 docs/archive/；删除 root-historical 21 个个人编码助手时代遗物；归档 21 个已完成 superpowers/plans 至 docs/archive/superpowers-2026-06/
- **findings.md 轮转**：拆分 2026-05 CQ-046 至 CQ-110 旧记录至 docs/archive/findings-2026-05.md（1094→204 行，148KB→18KB）
- ruff clean；核心测试 71 passed, 8 skipped
- route_policy backend 字段贯通（阶段 2 子项目 #5）：resolve_device_route_policy 复用 get_preferred_backend 填充 backend，route_policy 携带真实后端（如 dashscope_wanx）；固件 edge_c/edge_b schema 加可选 backend 字段
- Edge-C motion_task `route_policy` 硬契约（阶段 1 缺口 A）：schema required 化（固件 edge_c）+ 固件 DeviceServer 与云端 xiaozhi_compat 两条下行链路补 route_policy
- 双端语义统一：`CONTROL_CAPABILITIES` 重构为单一真相源（model_routing.py）并补 `estop`；固件 generate_route_policy 对齐云端 resolve（run_path→device_vector）
- 固件子模块指针更新至 esp32S_XYZ `a4cab61`；详见 findings.md 与 spec/plan

### 最近完成（2026-06-13）
- Legacy 路由/HTTP 栈退役（C9/C10）：`smart_router.py`、`router_http*.py`、`router_circuit_breaker.py`、`router_classifier.py`、`router_local.py` 等已移除
- `routing_intent.py` 承接意图分析，`analyze_intent()` 统一供编排与聊天入口使用
- ops_metrics 模块化重构完成（formatters/collectors/correlator）
- device_gateway/tasks.py 拆分完成（task_recorder.py）
- BACKENDS 单一来源修复完成
- 发布门清单和证据模板创建完成
- 阶段 1 设备路由契约：失败/阻止路径 `route_policy` 保留测试补齐

### 测试结果
```
185 passed (focused device+routing+ops suite)
27 passed (ops_metrics)
65 passed (device gateway)
5 passed (route_policy retention)
```

### 当前活跃路线图
- 旧“个人编码助手”优化路线图阶段 1-5 已关闭
- 新战略路线图见 [`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md)，当前处于阶段 1：稳定设备路由契约

## 退役模块

| 模块 | 状态 | 说明 |
|------|------|------|
| LiMa Code CLI (deepcode-cli) | ✅ 已退役 | 子模块已移除 |
| Telegram bot/operator | ✅ 已退役 | 路由/webhook 已移除 |
| WeChat 集成 | ✅ 已退役 | 桥接代码已归档 |
| agent_runtime 路由 | ✅ 已退役 | HTTP 路由已移除 |

## 部署状态

- **主 VPS**: Alibaba Cloud 47.112.162.80
- **备用节点**: JDCloud 117.72.118.95
- **公网健康检查**: chat.donglicao.com/health = 200
- **设备网关**: chat.donglicao.com/device/v1/health = 200

## 代码质量

| 项目 | 状态 |
|------|------|
| P0 违规 | ✅ 已修复 |
| xiaozhi_v1_compat 重构 | ✅ 完成 (1184→518, 7 模块) |
| admin_ui 模块化 | ✅ 完成 (482→55, 4 模块) |
| ops_metrics 重构 | ✅ 完成 (3 模块拆分) |
| tasks.py 拆分 | ✅ 完成 (task_recorder.py) |
| legacy 路由/HTTP 栈退役 | ✅ 完成 |

## 已知技术债务与注意事项

- **启动时间**：VPS 启动需 2-3 分钟，主要消耗在 backend profile / retirement 历史数据分析；非阻塞，但 health wait 较长
- **隐式模块依赖**：`routing_executor.py` 通过 `re.budget_manager` / `re.health_tracker` 访问模块属性，建议后续改为显式导入

- **本地/远程双环境**：Windows 本地代理后端、FRP `:8088`、VPS 直接后端共存，新增后端需明确拓扑归属
- **findings 历史**：2026-05 CQ-046~CQ-110 旧记录已归档至 `docs/archive/findings-2026-05.md`；当前 findings.md 仅保留 2026-06-09 战略转型后记录

## 关键文档

| 文档 | 用途 | 优先级 |
|------|------|--------|
| `docs/README.md` | 文档唯一入口与权威规则 | 必读 |
| `STATUS.md` | 当前状态（本文件） | 必读 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 当前活跃路线图 | 必读 |
| `AGENTS.md` | 开发约定与命令 | 必读 |
| `docs/ARCHITECTURE.md` | 系统架构 | 推荐 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 请求管线权威说明 | 推荐 |

| 文档 | 用途 |
|------|------|
| `docs/ARCHITECTURE.md` | 系统架构 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 请求管道权威文档 |

| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由指南 |
| `docs/RELEASE_GATE_CHECKLIST.md` | 发布门清单 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 优化路线图 |
