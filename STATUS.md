# LiMa Status

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com, api.donglicao.com
> **部署**: Alibaba Cloud VPS + JDCloud 备用

> Updated: 2026-06-15
> Branch: `design/route-policy-backend-field`
> Tests: 代码质量治理聚焦门 **112+83+22 passed**（Q0–Q3 / Q6 / Q7 切片）；device 套件 **452 passed**（M5–M8）；ruff clean
> Quality: Q0–Q7 代码质量治理计划 **已关闭**；P13 CI 门恢复；仓库规模统计已校正（~805 文件 / ~98k 行）

## 当前项目状态

### 核心功能
- **设备网关**: ESP32 绘图机/写字机云端控制
- **AI 路由**: 170+ 后端智能路由（设备任务 + 聊天/编码）
- **任务管理**: 任务创建、派发、执行、监控、恢复
- **设备策略**: 安全策略、固件兼容性、路径验证、route_policy/backend 字段贯通

### 最近完成（2026-06-15）Hardware AI Phase 1 M5–M8 Closeout + 清理

- **M5 Recovery + Reliability**：`execute_recovery()` 实现 retry/home/stop 决策；重试耗尽后 action 改为 `"stop"`；retry 任务 WS 直发时从 pending queue 移除，避免双发；task store 增加 `increment_retry_count` / `reset_task_for_retry` / `remove_pending_task`；`RedisDeviceTaskStore` 补齐相同协议
- **M6 Memory + Continuous Learning**：新增 `device_memory/extractor.py` / `consolidation.py` / `recall.py` / `quality_gates.py` / `store.py` / `routes/device_memory.py`；terminal 事件自动提取 episode 与 failure pattern；episode ID 加入 `event_id` 防止重试历史覆盖；memory 提取失败改为 `logger.warning`（符合 AGENTS.md 无静默降级）；`MemoryStore` 加 RLock 并标注生产化 TODO
- **M7 External Enrichment + Support/Ops**：`device_support/snapshot.py` 提供 shadow/firmware/self-check/近期终端任务/故障告警/脱敏建议；support snapshot 过滤 24h 时间窗口；`external_enrichment` 天气/节假日 provider 验证可用
- **M8 OTA + Release Gate**：`device_ota/release.py` + `canary.py` + `routes/device_ota.py`；新增 `/deploy/{version}`、`/canary/record-success/{device_id}`、`/canary/record-failure/{device_id}`、`DELETE /canary/devices/{device_id}`；未知 criteria 返回 400；gate 未就绪时 deploy 返回 412；部署新版本自动重置 canary 计数
- **代码审查修复**：review 发现的 6 个 P0/P1 问题全部修复，新增 20+ 测试覆盖去重、Redis store 协议、OTA 路由、support 时间窗口
- **死区代码清理**：删除 `routes/ops_probe_ingest.py`、`converters/anthropic_format.py`、`deploy/key_rotation.py`、`scripts/vps_eval_smoke_remote.py` 等 4 个死文件
- **Anthropic 残留清理**：移除 `/v1/messages` 端点及所有 Anthropic 转换函数（chat_endpoints.py 363→142 行）；route_registry.py 移除 4 个 anthropic 字段 + 7 个 agent_* 硬编码 False
- **配置死路径清理**：pyrightconfig.json 移除 agent_runtime/voice_gateway/code_orchestrator_context 等 8 个不存在的 include/exclude 路径；ruff.toml 移除 8 个不存在 exclude 路径；deploy_unified.py 移除 agent_runtime core dir + m1m5 slice + eval smoke 代码
- **文档清理**：归档 task_plan.md、OPS_ENTRYPOINTS_CN.md、FREE_MODEL_ROUTING_STATUS_CN.md、MODEL_CATALOG.md、ROUTING_ENGINE_DESIGN.md、PLAN_CLOSURE_STATUS.md 至 docs/archive/；删除 root-historical 21 个个人编码助手时代遗物；归档 21 个已完成 superpowers/plans 至 docs/archive/superpowers-2026-06/
- **findings.md 轮转**：拆分 2026-05 CQ-046 至 CQ-110 旧记录至 docs/archive/findings-2026-05.md（1094→204 行，148KB→18KB）
- **route_policy backend 字段贯通**：`resolve_device_route_policy` 复用 `get_preferred_backend` 填充 backend，route_policy 携带真实后端（如 dashscope_wanx）；固件 edge_c/edge_b schema 加可选 backend 字段
- **Edge-C motion_task route_policy 硬契约**：schema required 化（固件 edge_c）+ 固件 DeviceServer 与云端 xiaozhi_compat 两条下行链路补 route_policy
- **双端语义统一**：`CONTROL_CAPABILITIES` 重构为单一真相源（model_routing.py）并补 `estop`；固件 generate_route_policy 对齐云端 resolve（run_path→device_vector）
- **固件子模块指针**：更新至 esp32S_XYZ `a4cab61`；详见 findings.md 与 spec/plan

### 最近完成（2026-06-15）代码质量治理 Q0–Q7 Closeout

权威计划：[`docs/superpowers/plans/2026-06-15-code-quality-governance-plan.md`](docs/superpowers/plans/2026-06-15-code-quality-governance-plan.md)

- **Q0 统计/CI**：`repo_stats.py` 排除 `.venv*`；`CLAUDE.md` 规模更正；P13 静默 `except: pass` 门恢复
- **Q1 route_policy**：`esp32s_adapter` 委托 `resolve_device_route_policy`（`run_path`→`device_vector`）
- **Q2 tasks 拆分**：`device_gateway/tasks.py` 521→68 行 facade + task_creation/events/lifecycle/deps
- **Q3 routing_executor**：显式 `import health_tracker` / `budget_manager`
- **Q4 Store 生产化**：Memory/Ledger env 切换（`memory|redis`）；health 暴露 store 后端
- **Q5 超标文件拆分**：channel_gateway、orchestrate、admin_api_extra、eval_loop→scripts、routing_intent、speculative
- **Q6 测试卫生**：`test_provider_automation` / `test_ops_metrics` 拆为 4+4 域文件；`tests/README.md` 聚焦/全量门
- **Q7 战略评估**：[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](docs/CODEBASE_SUBSYSTEM_TIER_CN.md) hot/warm/cold 分层

### 测试结果（治理切片）

```text
Q0–Q3 聚焦: 112 passed
Q6 拆分套件: 83 passed, 1 skipped
Q7 文档验证切片: 22 passed
聚焦 device 套件: 452 passed
ruff check: clean（触及文件）
公网 health: https://chat.donglicao.com/health = 200
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
| Anthropic `/v1/messages` 兼容层 | ✅ 已退役 | 端点与转换函数已移除 |

## 部署状态

- **主 VPS**: Alibaba Cloud 47.112.162.80
- **备用节点**: JDCloud 117.72.118.95
- **公网健康检查**: chat.donglicao.com/health = 200
- **设备网关**: chat.donglicao.com/device/v1/health = 200
- **VPS 启动耗时**: 约 7 分钟（backend retirement / probe loop 历史数据分析预热），之后服务完全可用

## 代码质量

| 项目 | 状态 |
|------|------|
| P0 违规 | ✅ 已修复 |
| xiaozhi_v1_compat 重构 | ✅ 完成 (1184→518, 7 模块) |
| admin_ui 模块化 | ✅ 完成 (482→55, 4 模块) |
| ops_metrics 重构 | ✅ 完成 (3 模块拆分) |
| tasks.py 拆分 | ✅ 完成 (task_recorder.py) |
| legacy 路由/HTTP 栈退役 | ✅ 完成 |
| route_policy backend 字段贯通 | ✅ 完成 |
| Edge-C route_policy 硬契约 | ✅ 完成 |
| 代码质量治理 Q0–Q7 | ✅ 已关闭（见 governance plan） |
| channel_gateway / orchestrate / admin 拆分 | ✅ 完成 |
| Memory/Ledger Redis 后端 | ✅ 完成（env 切换） |

## 已知技术债务与注意事项

- **启动时间**：VPS 启动需约 7 分钟，主要消耗在 backend profile / retirement 历史数据分析；这些初始化目前阻塞 lifespan 完成，导致 health 等待较长。后续应改为后台预热或并行启动。
- **本地/远程双环境**：Windows 本地代理后端、FRP `:8088`、VPS 直接后端共存，新增后端需明确拓扑归属
- **context_pipeline 膨胀**：Hot 五模块外仍有大量 Cold 实验代码；见 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` P0–P4 建议
- **findings 历史**：2026-05 CQ-046~CQ-110 旧记录已归档至 `docs/archive/findings-2026-05.md`；当前 findings.md 仅保留 2026-06-09 战略转型后记录

## 关键文档

| 文档 | 用途 | 优先级 |
|------|------|--------|
| `docs/README.md` | 文档唯一入口与权威规则 | 必读 |
| `STATUS.md` | 当前项目状态（本文件） | 必读 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 当前活跃路线图 | 必读 |
| `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` | 子系统 hot/warm/cold 分层 | 推荐 |
| `AGENTS.md` | 开发约定与命令 | 必读 |
| `docs/ARCHITECTURE.md` | 系统架构 | 推荐 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 生产路由所有权 | 推荐 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由策略 | 推荐 |
| `docs/ESP32S_XYZ_MANAGEMENT_CN.md` | 产品子模块边界 | 推荐 |
| `docs/LIMA_MEMORY_CN.md` | 持久跨会话记忆 | 推荐 |
