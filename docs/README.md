# LiMa Documentation

> Updated: 2026-06-10

## Quick Start

LiMa 已从"编码助手"战略转型到"AI 智能设备统一云端服务"（2026-06-09 启动）。

| What you need | Read this |
|---------------|-----------|
| 项目全貌 | [`../STATUS.md`](../STATUS.md) |
| 开发规范 | [`../CLAUDE.md`](../CLAUDE.md) |
| 部署约定 | [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md) |
| 长期记忆 | [`LIMA_MEMORY.md`](LIMA_MEMORY.md) |
| 战略转型 | [`superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md`](superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md) |

## Architecture

| Document | Content |
|----------|---------|
| `ARCHITECTURE.md` | 系统架构总览 |
| `ROUTING_ENGINE_DESIGN.md` | 路由引擎设计 |
| `REQUEST_PIPELINE_AUTHORITY.md` | 请求管线权威边界 |
| `OBSERVABILITY_EVENTS.md` | 可观测性事件模型 |

## Operations

| Document | Content |
|----------|---------|
| `DEPLOY_AND_RELEASE_CONVENTION.md` | 自动部署 + 发布约定 |
| `OPS_ENTRYPOINTS.md` | 运维入口 |
| `WORKSPACE_HYGIENE.md` | 工作区卫生 |
| `ALIYUN_PROMETHEUS_DEPLOYMENT.md` | 阿里云 Prometheus 监控 |

## Device & Hardware

| Document | Content |
|----------|---------|
| `ESP32S_XYZ_MANAGEMENT.md` | ESP32/硬件子模块 |
| `MODEL_CATALOG.md` | 模型目录 |
| `FREE_MODEL_ROUTING_STATUS.md` | 免费模型路由状态 |

## Strategic Plans (Active)

| Document | Content |
|----------|---------|
| `superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md` | 战略转型总纲 |
| `superpowers/plans/2026-06-09-lima-hardware-ai-capability-redesign.md` | 硬件 AI 能力重设计 |
| `superpowers/plans/2026-06-09-lima-hardware-ai-phase1-execution-plan.md` | Phase 1 执行计划 |
| `superpowers/plans/2026-06-09-ai-drawing-writing-robot.md` | AI 绘图/写字机设计 |
| `superpowers/plans/2026-06-09-writing-robot-lightweight-backend.md` | 轻量级后端 |

## Work Logs

| Document | Content |
|----------|---------|
| `../progress.md` | 执行进展 |
| `../findings.md` | 事实发现 |
| `../PHASE0_COMPLETION_REPORT.md` | Phase 0 完成报告 |

## Archived

| Directory | Content |
|-----------|---------|
| `archive/phase0-2026-06/` | Phase 0 代码精简里程碑 |
| `archive/jdcloud-2026-06/` | 京东云监控部署项目 |
| `archive/superpowers-2026-05/` | 2026-05 历史计划 |
| `reference/` | 参考资料 |

## Documentation Statistics

- **Total documents**: 98 (.md files)
- **Top-level docs**: 18 (core references)
- **Active strategic plans**: 7 (superpowers/plans/)
- **Archived projects**: 3 directories

## Document Lifecycle

```
plan.md → execution → report.md → merge to progress.md → delete
                                                        ↓
                                              completed project
                                                        ↓
                                        archive/{project}-{YYYY-MM}/
```

See `DOCUMENTATION_CLEANUP_PLAN.md` for details.
