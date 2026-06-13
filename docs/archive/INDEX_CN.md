# LiMa 中文文档索引

> 更新时间: 2026-06-10
> 本索引列出项目中的中文文档和已翻译的英文文档。

## 核心文档（中文）

| 文档 | 说明 | 路径 |
|------|------|------|
| 项目概述 | 项目定位、架构、快速开始 | [README.md](../README.md) |
| 开发规范 | 项目开发规范、技术栈、代码质量 | [CLAUDE.md](../CLAUDE.md) |
| 项目状态 | 当前项目状态、里程碑记录 | [STATUS.md](../STATUS.md) |
| 文档索引 | 文档目录和说明 | [docs/README.md](README.md) |
| 系统架构 | 系统架构全景图 | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| 部署约定 | 自动部署与发布约定 | [docs/DEPLOY_AND_RELEASE_CONVENTION.md](DEPLOY_AND_RELEASE_CONVENTION.md) |
| 路由引擎设计 | routing_engine.py 设计决策 | [docs/ROUTING_ENGINE_DESIGN.md](ROUTING_ENGINE_DESIGN.md) |

## 翻译文档（英文→中文）

| 原文档 | 翻译文档 | 说明 |
|--------|----------|------|
| [AGENTS.md](../AGENTS.md) | [AGENTS_CN.md](../AGENTS_CN.md) | AI 代理协作规范 |
| [docs/REQUEST_PIPELINE_AUTHORITY.md](REQUEST_PIPELINE_AUTHORITY.md) | [docs/REQUEST_PIPELINE_AUTHORITY_CN.md](REQUEST_PIPELINE_AUTHORITY_CN.md) | 请求管道权威文档 |
| [docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md](AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md) | [docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md](AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md) | AI 绘图/写字机模型路由指南 |
| [docs/ESP32S_XYZ_MANAGEMENT.md](ESP32S_XYZ_MANAGEMENT.md) | [docs/ESP32S_XYZ_MANAGEMENT_CN.md](ESP32S_XYZ_MANAGEMENT_CN.md) | ESP32S_XYZ 产品管理边界 |
| [docs/FREE_MODEL_ROUTING_STATUS.md](FREE_MODEL_ROUTING_STATUS.md) | [docs/FREE_MODEL_ROUTING_STATUS_CN.md](FREE_MODEL_ROUTING_STATUS_CN.md) | 免费模型路由状态 |
| [docs/OBSERVABILITY_EVENTS.md](OBSERVABILITY_EVENTS.md) | [docs/OBSERVABILITY_EVENTS_CN.md](OBSERVABILITY_EVENTS_CN.md) | 可观测性事件模型 |
| [docs/PROJECT_OPTIMIZATION_ROADMAP.md](PROJECT_OPTIMIZATION_ROADMAP.md) | [docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md](PROJECT_OPTIMIZATION_ROADMAP_CN.md) | 项目优化路线图 |
| [docs/ONLINE_DISTRIBUTIONS.md](ONLINE_DISTRIBUTIONS.md) | [docs/ONLINE_DISTRIBUTIONS_CN.md](ONLINE_DISTRIBUTIONS_CN.md) | 在线分布清单与边缘策略 |
| [docs/OPS_ENTRYPOINTS.md](OPS_ENTRYPOINTS.md) | [docs/OPS_ENTRYPOINTS_CN.md](OPS_ENTRYPOINTS_CN.md) | 运维入口（已被 ONLINE_DISTRIBUTIONS 取代） |
| [docs/LIMA_MEMORY.md](LIMA_MEMORY.md) | [docs/LIMA_MEMORY_CN.md](LIMA_MEMORY_CN.md) | 跨会话持久项目记忆（中文摘要） |

## 技术文档（英文/中文混合，部分已翻译）

| 文档 | 说明 | 路径 | 状态 |
|------|------|------|------|
| 模型目录 | 后端/模型目录 | [docs/MODEL_CATALOG.md](MODEL_CATALOG.md) | 已是中文 |
| 设备协议对齐 | 设备协议对齐文档 | [docs/device_protocol_alignment.md](device_protocol_alignment.md) | 已是中文 |
| 小智 LiMa 协议对齐 | 小智 LiMa 协议对齐 | [docs/xiaozhi_lima_protocol_alignment.md](xiaozhi_lima_protocol_alignment.md) | 已是中文 |
| 工作区卫生 | 工作区卫生规则 | [docs/WORKSPACE_HYGIENE.md](WORKSPACE_HYGIENE.md) | 已是中文 |
| 阿里云 Prometheus 部署 | 阿里云 Prometheus 监控部署 | [docs/ALIYUN_PROMETHEUS_DEPLOYMENT.md](ALIYUN_PROMETHEUS_DEPLOYMENT.md) | 已是中文 |

## 其他中文文档

| 文档 | 说明 | 路径 |
|------|------|------|
| 错误指纹 | 错误指纹分析 | [ERROR_FINGERPRINTS.md](../ERROR_FINGERPRINTS.md) |
| 项目学习报告 | 项目学习报告 | [PROJECT_LEARNING_REPORT.md](../PROJECT_LEARNING_REPORT.md) |
| Phase 0 完成报告 | Phase 0 完成报告 | [PHASE0_COMPLETION_REPORT.md](../PHASE0_COMPLETION_REPORT.md) |
| 路由特性 | 路由特性说明 | [ROUTING_FEATURES.md](../ROUTING_FEATURES.md) |
| AI 路由模型完整指南 | AI 路由模型完整指南 | [AI_ROUTING_MODEL_COMPLETE_GUIDE.md](../AI_ROUTING_MODEL_COMPLETE_GUIDE.md) |
| 所有系统提示词 | 所有系统提示词 | [ALL_SYSTEM_PROMPTS.md](../ALL_SYSTEM_PROMPTS.md) |
| 混淆分析 | 混淆分析 | [confusion_analysis.md](../confusion_analysis.md) |
| 实际系统提示词 | 实际系统提示词 | [cursor_actual_system_prompt.md](../cursor_actual_system_prompt.md) |

## 子项目文档

### esp32S_XYZ 文档

esp32S_XYZ 子项目包含大量中文文档，主要在 `esp32S_XYZ/docs/` 目录下。

### 其他子项目文档

- `_codegraph_repo/docs/` - CodeGraph 项目文档（英文）
- `esp32S_XYZ/firmware/u8-xiaozhi/docs/` - 固件文档（中英文）
- `esp32S_XYZ/server/xiaozhi-esp32-server/docs/` - 服务器文档（中英文）

## 文档统计

- **总文档数**: 557 个 Markdown 文件
- **中文文档**: 约 60% 已经是中文
- **英文文档**: 约 40% 需要翻译
- **已翻译**: 10 个核心文档 (AGENTS.md, REQUEST_PIPELINE_AUTHORITY.md, AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md, ESP32S_XYZ_MANAGEMENT.md, FREE_MODEL_ROUTING_STATUS.md, OBSERVABILITY_EVENTS.md, PROJECT_OPTIMIZATION_ROADMAP.md, ONLINE_DISTRIBUTIONS.md, OPS_ENTRYPOINTS.md, LIMA_MEMORY.md)
- **待翻译**: 0 个 docs 核心文档（所有 docs 目录下英文文档已翻译或原本已是中文）

## 翻译建议

1. **优先翻译**: 核心架构文档、API 文档、部署文档
2. **其次翻译**: 设备相关文档、运维文档
3. **最后翻译**: 历史归档文档、参考文档
4. **保持原样**: 代码注释、测试文档、临时文档

## 文档维护

- 新文档应优先使用中文编写
- 英文文档翻译后，建议在原文件名后添加 `_CN` 后缀
- 定期更新本索引，确保文档链接有效