# LiMa 文档索引

> 更新日期：2026-07-10
> 项目定位：DLC 绘图服务 —— 为 ESP32 绘图机/写字机提供云端路径生成、任务下发、设备管理，通过 MCP 与小智官方云（xiaozhi.me）集成。
>
> **瘦身声明**：旧多后端 AI 路由系统（server.py + routing_engine + router_v3 + chat/admin/voice/provider 探测）已在 P4/P5 瘦身中物理删除。当前生产入口为 `server_dlc:8081`。凡本索引未列出、且描述上述旧系统的文档，均已归入 `archive/`，仅作历史审计，不得作为当前决策依据。

## 必读顺序（新协作者）

1. [`../STATUS.md`](../STATUS.md) / [`PROJECT_STATUS_CN.md`](PROJECT_STATUS_CN.md) — 当前项目状态（二者同步）
2. [`../AGENTS.md`](../AGENTS.md) — 代码规范、命令、Git/部署约定、真实架构
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — 瘦身后系统架构与模块边界
4. [`DEVICE_DEVELOPER_GUIDE_CN.md`](DEVICE_DEVELOPER_GUIDE_CN.md) — 设备开发、联调、验证入口
5. [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md) — 部署与发布约定

## 快速入口

| 目标 | 文档 | 状态 |
| --- | --- | --- |
| 语音 API（公开文档） | [`../docs-site/api/voice.md`](../docs-site/api/voice.md) | ✅ 活跃（2026-07-10） |
| 语音设计规格 | [`superpowers/specs/2026-07-02-mini-program-voice-draw-design.md`](superpowers/specs/2026-07-02-mini-program-voice-draw-design.md) | ✅ 后端完成，真机待验 |
| 遗留待办 | [`superpowers/specs/2026-07-02-backlog-planning.md`](superpowers/specs/2026-07-02-backlog-planning.md) | ✅ 活跃 |
| 当前状态 | [`../STATUS.md`](../STATUS.md) / [`PROJECT_STATUS_CN.md`](PROJECT_STATUS_CN.md) | ✅ 2026-07-10 |
| 开发约定 | [`../AGENTS.md`](../AGENTS.md) / [`../CLAUDE.md`](../CLAUDE.md) | ✅ 活跃 |
| 真实架构总览 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | ✅ 活跃（2026-07-06 重写） |
| 设备开发入口 | [`DEVICE_DEVELOPER_GUIDE_CN.md`](DEVICE_DEVELOPER_GUIDE_CN.md) | ✅ 活跃（含 draw_generated 热路径） |
| 长期记忆 | [`LIMA_MEMORY_CN.md`](LIMA_MEMORY_CN.md) | ✅ 活跃（含历史快照，顶部有退役标注） |
| 发布规则 | [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md) | ✅ 活跃 |
| 发布检查清单 | [`RELEASE_GATE_CHECKLIST.md`](RELEASE_GATE_CHECKLIST.md) | ✅ 活跃 |
| 第一开发原则（Ponytail） | [`AGENTS_PONYTAIL.md`](AGENTS_PONYTAIL.md) | ✅ 活跃 |
| 第二开发原则（设计） | [`AGENTS_DESIGN_PRINCIPLES.md`](AGENTS_DESIGN_PRINCIPLES.md) | ✅ 活跃 |
| ECC 开发流程 | [`ECC_WORKFLOW_CN.md`](ECC_WORKFLOW_CN.md) | ✅ 活跃 |
| 历史执行进展 | [`../progress.md`](../progress.md) | 可选 |
| 事实发现日志 | [`../findings.md`](../findings.md) | 可选（append-only） |
| 语音 TDD 证据 | [`testing/device_app_voice.tdd.md`](testing/device_app_voice.tdd.md) | ✅ 2026-07-10 |

## 架构与设备

| 主题 | 文档 |
| --- | --- |
| 系统总览 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 语音 API | [`../docs-site/api/voice.md`](../docs-site/api/voice.md) |
| 设备开发入口 | [`DEVICE_DEVELOPER_GUIDE_CN.md`](DEVICE_DEVELOPER_GUIDE_CN.md) |
| ESP32S_XYZ 管理 | [`ESP32S_XYZ_MANAGEMENT_CN.md`](ESP32S_XYZ_MANAGEMENT_CN.md) |
| 小智云集成缺口 | [`XIAOZHI_INTEGRATION_GAP_CN.md`](XIAOZHI_INTEGRATION_GAP_CN.md) |
| 小智云 + DLC 瘦身设计 | [`xiaozhi-cloud/lima-slimdown-design.md`](xiaozhi-cloud/lima-slimdown-design.md) |
| 写字机稳定性计划 | [`WRITING_PLOTTER_STABILITY_PLAN.md`](WRITING_PLOTTER_STABILITY_PLAN.md) |

## 运维与发布

| 主题 | 文档 |
| --- | --- |
| 部署与发布约定 | [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md) |
| 发布检查清单 | [`RELEASE_GATE_CHECKLIST.md`](RELEASE_GATE_CHECKLIST.md) |
| 工作区卫生 | [`WORKSPACE_HYGIENE.md`](WORKSPACE_HYGIENE.md) |
| 在线分发 | [`ONLINE_DISTRIBUTIONS_CN.md`](ONLINE_DISTRIBUTIONS_CN.md) |
| 阿里云 DLC 入口 Runbook | [`ops/ALIYUN_DLC_ENTRY.md`](ops/ALIYUN_DLC_ENTRY.md) |
| JDCloud 运行状态 | [`ops/JDCLOUD_RUNTIME_STATUS.md`](ops/JDCLOUD_RUNTIME_STATUS.md) |
| AI→Motion 发布证据模板 | [`release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`](release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md) |

## 历史、归档与已过时

以下保留以供审计，但**不应作为当前决策依据**。旧多后端路由系统相关文档集中归档在 `archive/strategic-plans-2026-06/`：

| 主题 | 位置 | 说明 |
| --- | --- | --- |
| 旧系统架构（多后端路由） | [`archive/strategic-plans-2026-06/ARCHITECTURE_OLD_20260626.md`](archive/strategic-plans-2026-06/ARCHITECTURE_OLD_20260626.md) | 瘦身前架构 |
| 旧请求管线权威说明 | [`archive/strategic-plans-2026-06/REQUEST_PIPELINE_AUTHORITY_CN.md`](archive/strategic-plans-2026-06/REQUEST_PIPELINE_AUTHORITY_CN.md) | routing_engine 18 步流水线 |
| 旧 AI 绘图/写字模型路由指南 | [`archive/strategic-plans-2026-06/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_OLD_20260616.md`](archive/strategic-plans-2026-06/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_OLD_20260616.md) | 多后端路由时代 |
| 旧可观测事件模型 | [`archive/strategic-plans-2026-06/OBSERVABILITY_EVENTS_OLD_20260524.md`](archive/strategic-plans-2026-06/OBSERVABILITY_EVENTS_OLD_20260524.md) | 引用已删 routing_engine |
| 旧阿里云 pilot 部署 | [`archive/strategic-plans-2026-06/ALIYUN_PILOT_DEPLOY_ARCHIVED.md`](archive/strategic-plans-2026-06/ALIYUN_PILOT_DEPLOY_ARCHIVED.md) | lima-router-pilot 已退役 |
| 历史进展归档 | [`archive/progress-2026-05.md`](archive/progress-2026-05.md) | 2026-05-31 之前的 progress |
| 里程碑计划/规格快照 | [`superpowers/plans/`](superpowers/plans/)、[`superpowers/specs/`](superpowers/specs/) | 带日期，完成后归档 |
| 发布证据快照 | [`release_evidence/`](release_evidence/) | 带日期的历史发布证据 |
| 模型准入报告 | [`model_admission/`](model_admission/) | 带日期的历史准入评测 |
| 外部参考资料 | [`reference/`](reference/) | 外部项目/论文参考 |

## 工作日志

| 主题 | 文档 |
| --- | --- |
| 执行进展 | [`../progress.md`](../progress.md) |
| 事实发现 | [`../findings.md`](../findings.md) |
| 历史进展（2026-05） | [`archive/progress-2026-05.md`](archive/progress-2026-05.md) |
