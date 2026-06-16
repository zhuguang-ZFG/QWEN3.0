# LiMa Status

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com, api.donglicao.com
> **部署**: Alibaba Cloud VPS + JDCloud 备用

> Updated: 2026-06-17
> Branch: `main`
> Scale: 670 文件 / 79,447 行（较初始 794/93,145 减 124 文件 / 13,698 行）
> Tests: 全量 1645 passed / 24 skipped / 0 failed；ruff clean
> 注：`tests/test_device_draw_integration.py`、`tests/test_svg_converter.py` 因本地缺少 `cv2` 在收集阶段报错，非代码回归。
> VPS smoke：`https://chat.donglicao.com/health` 200；`/device/v1/health` 200（`auth_configured=true`，已配置测试设备 token）。

## 当前项目状态

### 核心功能
- **设备网关**: ESP32 绘图机/写字机云端控制
- **AI 路由**: 170+ 后端智能路由（设备任务 + 聊天/编码）
- **任务管理**: 任务创建、派发、执行、监控、恢复
- **设备策略**: 安全策略、固件兼容性、路径验证、route_policy/backend 字段贯通

### 当前开发文档入口（2026-06-16）

- **设备开发入口**：[`docs/DEVICE_DEVELOPER_GUIDE_CN.md`](docs/DEVICE_DEVELOPER_GUIDE_CN.md) 汇总设备联调、常用测试、证据要求和最小闭环。
- **下一阶段计划**：[`docs/superpowers/plans/2026-06-16-lima-author-intent-and-next-plan.md`](docs/superpowers/plans/2026-06-16-lima-author-intent-and-next-plan.md) 明确 G1–G4：AI→Motion 发布门、模型准入复跑、证据边界瘦身、启动/部署不确定性降低。
- **协议开发闭环**：[`docs/device_protocol_alignment.md`](docs/device_protocol_alignment.md) 已补充 `hello` → `task_dispatch` → `motion_event` → 终态证据的调试路径，并明确 `route_policy` 为下行任务硬契约。

### 最近完成（2026-06-17）可选 P5：GitHub/Gitee webhook 路由退役

- **删除**：`routes/github_webhook.py`、`routes/gitee_webhook.py`；`github_webhook/`、`gitee_webhook/` 包目录；`tests/test_github_webhook.py`、`tests/test_gitee_webhook.py`。
- **更新**：`routes/route_registry.py` 移除两个注册块；`scripts/check_vps_environment.py` 移除 webhook secret 检查；`tests/test_vps_environment_check.py` 改用 `LIMA_ADMIN_TOKEN` 示例；`.env.example` 移除 `GITHUB_WEBHOOK_*` / `GITEE_WEBHOOK_*`；`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 更新 P5 状态。
- **验证**：聚焦门 `pytest tests/test_retrieval_injection.py tests/test_routing_engine.py tests/test_device_gateway_model_routing.py tests/test_provider_automation_admission.py -q` → **77 passed**；`ruff check .` clean。
- **规模**：`python_files=670`，`python_lines=79,447`。

### 最近完成（2026-06-17）G1 后续：假 U1 运动执行闭环证据

- **新增测试**：`tests/test_fake_u1_cloud_loop.py`（3 cases）
  - 云端 `home` / `write hi` 命令经 `/device/v1/tasks` → WebSocket `task_dispatch` → `fake_device_server` → fake U1 TCP 执行 → `/device/v1/events` 终态 `done`。
  - 校验 `motion_task` 到 Edge-D 命令序列的转换契约。
- **验证**：`pytest tests/test_fake_u1_cloud_loop.py -v` → **3 passed**；`ruff check` clean。
- **证据更新**：`docs/release_evidence/2026-06-16-M13-AI-to-Motion-release-gate.md` 门 B「假 U1 运动执行」状态改为 ✅。

### 最近完成（2026-06-17）G4 启动与部署不确定性降低

- **目标**：降低启动和部署不确定性，把耗时任务拆分为 ready 必须完成与 warming 可后台完成。
- **发现**：
  - 通过 `server_lifespan.py` 阶段日志定位到真正瓶颈：**`context_pipeline.auto_indexer` 在事件循环中运行，ChromaDB/ONNX 模型下载/解压阻塞了主事件循环**，导致 `/health` 长时间无法 ready。
  - 次要瓶颈：`channel_retirement.telegram` 同步调用 Telegram API 耗时约 1.7s。
- **修复**：
  - `context_pipeline/auto_indexer.py`：把 `_indexer_loop` 从 asyncio task 改为 daemon thread，扫描（含 ChromaDB 初始化）不再阻塞事件循环。
  - `server_lifespan.py`：把 `retire_telegram_webhook_from_env()` 改为 `asyncio.create_task` 后台执行。
- **结果**：
  - VPS 启动从约 **7 分钟** 降至约 **8 秒**（systemctl start → `/health` 200）。
  - `/health` 返回 `startup.status=ready` 和 `startup.phases` 数组。
  - 公网 smoke：`https://chat.donglicao.com/health` 200；`/device/v1/health` 200。
- **验证**：
  - `pytest tests/test_routing_engine.py tests/test_system_endpoints.py tests/test_retrieval_injection.py -q` → **34 passed**。
  - `ruff check server_lifespan.py context_pipeline/auto_indexer.py routes/system_endpoints.py` → clean。

### 最近完成（2026-06-17）G3 证据边界瘦身（小批）

- **目标**：沿证据边界删除一个冷区模块，保护热路径。
- **审计**：`python scripts/codegraph_orphans.py --fanin` 识别 `eval_status.py` 为 ORPHAN。
- **删除**：`eval_status.py`（115 行）；保留与其余 eval 模块有依赖的 `eval_pinned_call.py`、`eval_preflight.py`、`eval_quiet.py` 等。
- **验证**：eval 聚焦套件 23 passed / `ruff check .` clean / CodeGraph + ripgrep 确认无生产引用。

### 最近完成（2026-06-17）G2 设备模型准入复跑

- **目标**：执行作者意图计划 G2，让 `device_draw` / `device_vector` / `device_write` / `device_control` 的准入依据可复跑、可比较、可回滚。
- **修复**：原 `docs/model_admission/2026-06-16-device-drawing-writing.md` 因 Windows 控制台重定向编码错误变为 ISO-8859 二进制损坏，已删除并重建为 `docs/model_admission/2026-06-17-device-drawing-writing.md`。
- **报告**：按 `docs/model_admission/TEMPLATE.md` 补齐元数据、角色详情、路由偏好配置、准入门控和可复现命令。
- **验证**：
  - `python scripts/eval_device_model_role.py --all` → 6 角色 admit/admit_conditional，2 角色 defer，0 fail。
  - `pytest tests/test_device_gateway_model_routing.py -q` → **32 passed**。
  - `pytest tests/test_routing_engine.py -q --tb=short` → **24 passed**。
  - `ruff check` 触及文件 clean。
- **文档同步**：`docs/README.md` 最新准入报告索引更新为 2026-06-17 版本。

### 最近完成（2026-06-17）第二轮瘦身：零引用模块 + 归档脚本清理

> 两轮合计：794→684 文件（-110），93,145→80,546 行（-12,599）

- **14 个零生产引用模块删除**：`coding_eval`、`edit_protocol`、`esp32s_adapter/`、`eval_call`、`eval_digest`、`eval_registry`、`free_web_ai_admission`、`health_summary`、`healthchecks_io`、`mimo_stt`、`notify/`、`request_context_preflight`、`streaming_events`、`converters/` + 对应测试
- **归档脚本清理**：`scripts/archive/` 13 个文件（deploy_legacy + openclaw_retired + key_rotation_legacy）
- **配置同步**：`codegraph_orphans.py`、`pyrightconfig.json`、`ruff.toml` 移除已删模块条目
- **测试修复**：`test_eval_topology.py` 移除 `eval_call` 测试；`test_secret_hygiene.py` 移除归档断言
- **验证**：ruff clean；全量测试 1637 passed / 24 skipped / 4 pre-existing failures

### 最近完成（2026-06-17）大子系统审计瘦身

> 审计范围：`search_gateway`、`channel_gateway`、`routes/` + 全仓冷模块扫描
> 详见 [`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §13 和 [`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md) P6

- **channel_gateway 整体退役**：23 文件 + `routes/channel_gateway.py` + 13 测试删除；`route_registry.py` 注册块移除；`channel_retirement.py` RETIRED_CHANNELS 标记
- **冷模块清理**：`research/`、`web_reverse_eval.py`、`cli_status.py`、`sandbox/`、`data_workbench/`、`ops_entrypoint/` 共 6 个模块 + 测试删除
- **search_gateway 死适配器**：`zhihu_adapter.py`、`public_feeder.py`、`codesearch_status.py`、`policy.py` 删除
- **空目录与死 shim**：`eval_loop.py` 删除；`evals/`、`fragments/`、`reverse_gateway/`、`routes/.omc/` 清理
- **配置同步**：`pyrightconfig.json`、`deploy_unified.py`、`codegraph_orphans.py` 移除 channel_gateway 条目
- **验证**：ruff clean；全量测试 1736 passed / 25 skipped / 4 pre-existing failures（无新增）

### 最近完成（2026-06-16）阶段 2 续 — Image Generator 真实 API 夹具

- **`tests/test_dashscope_image_live.py`**：Wanx 同步 + 异步轮询；`ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1` 启用
- **`eval_device_model_role.py --live`**：image_generator 合并 live 目标；默认离线 7 passed
- **文档**：`docs/model_admission/TEMPLATE.md`、`.env.example`、`2026-06-16-device-drawing-writing.md`
- **验证**：`pytest tests/test_eval_device_model_role.py tests/test_dashscope_image_client.py tests/test_dashscope_image_live.py` → **12 passed**（live 无密钥时 skip）

### 最近完成（2026-06-16）M13 AI→Motion 发布证据模板

- **重写** `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`：对齐门 A–F、`RELEASE_GATE_CHECKLIST`、假 U8 环与真实 pytest 命令；替换原通用占位表
- **新增** `docs/release_evidence/README.md`；`docs/README.md` 索引
- **验证**：`pytest tests/test_device_gateway_model_routing.py` + `test_fake_u8_hello_heartbeat_transcript_motion_event_loop` → **33 passed**

### 最近完成（2026-06-16）M9–M12 设备路由与准入

- **M9 假 U8 消费 route_policy**：固件 `fake_lima_u8` 硬契约解析 + JSONL 证据；主仓稳定性门测试对齐
- **M10 路由制品证据**：`task_recorder` 全场景 `route_evidence`（创建/阻止/验证失败/恢复/终端消费）
- **M11 模型准入脚手架**：`docs/model_admission/TEMPLATE.md` + `scripts/eval_device_model_role.py`（8 角色评测）
- **M12 Profile 路由输入**：`enrich_route_policy_with_profile()` 接入 `resolve_device_route_policy()`；不完整 profile 审批门控
- **准入快照**：`docs/model_admission/2026-06-16-device-drawing-writing.md`

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

权威计划：[`docs/archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md`](docs/archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md)

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
- 新战略路线图见 [`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md)，M9–M12 已关闭；下一阶段 M13 发布证据模板

## 退役模块

| 模块 | 状态 | 说明 |
|------|------|------|
| LiMa Code CLI (deepcode-cli) | ✅ 已退役 | 子模块已移除 |
| Telegram bot/operator | ✅ 已退役 | 路由/webhook 已移除 |
| WeChat 集成 | ✅ 已退役 | 桥接代码已归档 |
| agent_runtime 路由 | ✅ 已退役 | HTTP 路由已移除 |
| Anthropic `/v1/messages` 兼容层 | ✅ 已退役 | 端点与转换函数已移除 |
| channel_gateway（WeChat 绑定层） | ✅ 已退役 | 2026-06-17；23 文件 + 路由 + 13 测试删除；`channel_retirement.py` 标记 |

## 部署状态

- **主 VPS**: Alibaba Cloud 47.112.162.80
- **备用节点**: JDCloud 117.72.118.95
- **公网健康检查**: chat.donglicao.com/health = 200（2026-06-16 19:15 恢复；此前因 `device_ledger.store` 缺失 `configure_ledger_store_from_env` 导致 systemd 反复崩溃）
- **设备网关**: chat.donglicao.com/device/v1/health = 200
- **VPS 启动耗时**: 约 7 分钟（backend retirement / probe loop 历史数据分析预热），之后服务完全可用
- **最近恢复操作**: 部署 15 个 store/memory/notifier/gateway/lifespan 文件，备份 `/opt/lima-router/backups/unified-files-20260616_190649/runtime-before.tgz`

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
| `docs/DEVICE_DEVELOPER_GUIDE_CN.md` | 设备开发、联调、验证入口 | 必读 |
| `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` | 子系统 hot/warm/cold 分层 | 推荐 |
| `AGENTS.md` | 开发约定与命令 | 必读 |
| `docs/ARCHITECTURE.md` | 系统架构 | 推荐 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 生产路由所有权 | 推荐 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由策略 | 推荐 |
| `docs/ESP32S_XYZ_MANAGEMENT_CN.md` | 产品子模块边界 | 推荐 |
| `docs/LIMA_MEMORY_CN.md` | 持久跨会话记忆 | 推荐 |
