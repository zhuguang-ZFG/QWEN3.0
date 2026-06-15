# LiMa 文档索引

> 更新日期：2026-06-15
> 项目定位：AI 智能设备统一云端服务
>
> **权威规则**：本索引列出当前有效的文档。若某文档被标注为“历史/归档”，则以当前有效文档为准；若存在冲突，以本索引中“当前状态”与“路线图”两类文档为最新依据。

## 必读顺序（新协作者）

1. [`../STATUS.md`](../STATUS.md) — 当前项目状态、已完成项、退役模块、部署健康
2. [`PROJECT_OPTIMIZATION_ROADMAP_CN.md`](PROJECT_OPTIMIZATION_ROADMAP_CN.md) — 当前活跃路线图与阶段目标
3. [`../AGENTS.md`](../AGENTS.md) — 代码规范、命令、Git/部署约定
4. [`ARCHITECTURE.md`](ARCHITECTURE.md) — 系统架构与模块边界
5. [`REQUEST_PIPELINE_AUTHORITY_CN.md`](REQUEST_PIPELINE_AUTHORITY_CN.md) — 请求处理管线权威说明

## 快速入口

| 目标 | 文档 | 状态 |
| --- | --- | --- |
| 当前状态 | [`../STATUS.md`](../STATUS.md) | ✅ 活跃 |
| 开发约定 | [`../CLAUDE.md`](../CLAUDE.md) | ✅ 活跃 |
| 长期记忆 | [`LIMA_MEMORY_CN.md`](LIMA_MEMORY_CN.md) | ✅ 活跃 |
| 项目路线图 | [`PROJECT_OPTIMIZATION_ROADMAP_CN.md`](PROJECT_OPTIMIZATION_ROADMAP_CN.md) | ✅ 活跃 |
| 子系统热度分层（瘦身评估） | [`CODEBASE_SUBSYSTEM_TIER_CN.md`](CODEBASE_SUBSYSTEM_TIER_CN.md) | ✅ 活跃（Q7） |
| Cold 清理优先级（下一批删/迁） | [`CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](CODEBASE_COLD_PRUNE_PRIORITY_CN.md) | ✅ 活跃（CP-0 规划） |
| context_pipeline 模块地图 | [`../context_pipeline/README.md`](../context_pipeline/README.md) | ✅ 活跃 |
| provider_probe（Cold 离线） | [`../provider_probe/README.md`](../provider_probe/README.md) | ✅ 活跃 |
| 发布规则 | [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md) | ✅ 活跃 |
| 历史执行进展 | [`../progress.md`](../progress.md) | ✅ 活跃（近 3 个月） |
| 旧任务计划 | [`../task_plan.md`](../task_plan.md) | ⚠️ 部分过时，仅作历史参考 |

## 架构与请求链路

| 主题 | 文档 |
| --- | --- |
| 系统总览 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 请求管线权威说明 | [`REQUEST_PIPELINE_AUTHORITY_CN.md`](REQUEST_PIPELINE_AUTHORITY_CN.md) |
| 路由引擎设计 | [`archive/ROUTING_ENGINE_DESIGN.md`](archive/ROUTING_ENGINE_DESIGN.md)（历史归档） |
| 可观测事件 | [`OBSERVABILITY_EVENTS_CN.md`](OBSERVABILITY_EVENTS_CN.md) |

## 设备与模型

| 主题 | 文档 |
| --- | --- |
| 绘图/写字模型路由 | [`AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md`](AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md) |
| ESP32S_XYZ 管理 | [`ESP32S_XYZ_MANAGEMENT_CN.md`](ESP32S_XYZ_MANAGEMENT_CN.md) |
| 设备协议对齐 | [`device_protocol_alignment.md`](device_protocol_alignment.md) |
| 模型目录 | [`archive/MODEL_CATALOG.md`](archive/MODEL_CATALOG.md)（历史归档） |
| 免费模型路由状态 | [`archive/FREE_MODEL_ROUTING_STATUS_CN.md`](archive/FREE_MODEL_ROUTING_STATUS_CN.md)（历史归档） |

## 运维与发布

| 主题 | 文档 |
| --- | --- |
| 工作区卫生 | [`WORKSPACE_HYGIENE.md`](WORKSPACE_HYGIENE.md) |
| 在线分发 | [`ONLINE_DISTRIBUTIONS_CN.md`](ONLINE_DISTRIBUTIONS_CN.md) |
| 发布检查清单 | [`RELEASE_GATE_CHECKLIST.md`](RELEASE_GATE_CHECKLIST.md) |
| Prometheus 部署 | [`ALIYUN_PROMETHEUS_DEPLOYMENT.md`](ALIYUN_PROMETHEUS_DEPLOYMENT.md) |

> 注：`OPS_ENTRYPOINTS_CN.md` 已被 `ONLINE_DISTRIBUTIONS_CN.md` 取代为主要在线分发入口；旧运维入口仅作历史参考。

## 近期计划

| 主题 | 文档 |
| --- | --- |
| route_policy backend 字段贯通 | [`archive/superpowers-2026-06/2026-06-15-route-policy-backend-field.md`](archive/superpowers-2026-06/2026-06-15-route-policy-backend-field.md)（已关闭归档） |
| Edge-C route_policy 硬契约 | [`archive/superpowers-2026-06/2026-06-15-edge-c-route-policy-hard-contract.md`](archive/superpowers-2026-06/2026-06-15-edge-c-route-policy-hard-contract.md)（已关闭归档） |
| 代码质量治理 Q0–Q7 | [`archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md`](archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md)（已关闭归档） |
| 智能设备战略转型 | [`superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md`](superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md)（历史参考） |
| Phase 2 代码瘦身 | [`superpowers/plans/2026-06-12-phase2-code-simplification-plan.md`](superpowers/plans/2026-06-12-phase2-code-simplification-plan.md)（Slice 1–2 已关闭） |

## 历史、归档与已过时

以下文档保留以供审计，但不应作为当前决策依据：

| 主题 | 文档 | 说明 |
| --- | --- | --- |
| 旧个人编码助手计划 | [`archive/task_plan.md`](archive/task_plan.md) | 已归档；战略转型前制定，其中 server.py 分解、BACKENDS 单一来源、key_pool 接入等项已完成或方向已变 |
| 历史进展归档 | [`archive/progress-2026-05.md`](archive/progress-2026-05.md) | 2026-05-31 之前的 `progress.md` 记录 |
| Phase 2 代码瘦身报告 | [`archive/phase2/`](archive/phase2/) | smart_router 迁移与代码精简执行报告 |
| Stage 1-2 交付报告 | [`archive/STAGE_1_2_DELIVERY_REPORT.md`](archive/STAGE_1_2_DELIVERY_REPORT.md) | 2026-06-11 设备协议/智能/协同交付报告 |
| 旧模型准入报告 | [`archive/MODEL_ADMISSION_REPORT_2026-06.md`](archive/MODEL_ADMISSION_REPORT_2026-06.md) | 早期通用后端准入草稿，当前以 `model_admission/` 下报告为准 |
| 准入报告模板 | [`model_admission/TEMPLATE.md`](model_admission/TEMPLATE.md) | 复制后填写；评测命令见 `scripts/eval_device_model_role.py` |
| 最新准入报告 | [`model_admission/2026-06-16-device-drawing-writing.md`](model_admission/2026-06-16-device-drawing-writing.md) | eval 脚本自动生成快照 |
| 历史切片 | [`superpowers/plans/`](superpowers/plans/) | 按里程碑记录，完成后即归档 |
| 参考资料 | [`reference/`](reference/) | 外部项目/论文参考 |

## 工作日志

| 主题 | 文档 |
| --- | --- |
| 执行进展 | [`../progress.md`](../progress.md) |
| 历史进展（2026-05） | [`archive/progress-2026-05.md`](archive/progress-2026-05.md) |
| 事实发现 | [`../findings.md`](../findings.md) |
