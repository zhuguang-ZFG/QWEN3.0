# LiMa Memory

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com, api.donglicao.com
> **部署**: Alibaba Cloud VPS + JDCloud 备用

> Updated: 2026-06-13
> Branch: `main`
> Tests: **2009+ tests** (185 in focused device+routing+ops suite)

## 项目架构

### 核心模块
- `routing_engine.py` (287L): 统一路由入口
- `device_gateway/tasks.py` (~380L): 设备任务管理
- `device_gateway/task_recorder.py` (107L): 任务录制辅助
- `device_gateway/model_routing.py` (~243L): 设备模型路由
- `device_gateway/profiles.py` (~191L): 设备配置文件
- `routes/ops_metrics.py` (~284L): 运维指标端点

### 请求管道
1. **Chat/AI 管道**: routing_engine → 后端选择 → http_caller
2. **设备任务管道**: intent → path_pipeline → path_validator → policy → MQTT → ESP32

### 部署拓扑
- **主 VPS**: Alibaba Cloud 47.112.162.80
- **备用节点**: JDCloud 117.72.118.95
- **公网端点**: chat.donglicao.com, api.donglicao.com

## 退役模块

| 模块 | 状态 | 说明 |
|------|------|------|
| LiMa Code CLI (deepcode-cli) | ✅ 已退役 | 子模块已移除 |
| Telegram bot/operator | ✅ 已退役 | 路由/webhook 已移除 |
| WeChat 集成 | ✅ 已退役 | 桥接代码已归档 |
| agent_runtime 路由 | ✅ 已退役 | HTTP 路由已移除 |

## 优化路线图（全部完成）

| 阶段 | 目标 | 状态 |
|------|------|------|
| 阶段 1 | 稳定设备路由契约 | ✅ 完成 |
| 阶段 2 | 按角色准入 AI 绘图/写字模型 | ✅ 完成 |
| 阶段 3 | 设备配置文件成为一级路由输入 | ✅ 完成 |
| 阶段 4 | 加固通用 LLM 路由 | ✅ 完成 |
| 阶段 5 | 构建 AI 到运动的发布门 | ✅ 完成 |

## 代码质量

| 项目 | 状态 |
|------|------|
| P0 违规 | ✅ 已修复 |
| ops_metrics 重构 | ✅ 完成 (3 模块拆分) |
| tasks.py 拆分 | ✅ 完成 (task_recorder.py) |
| BACKENDS 单一来源 | ✅ 完成 |

## 关键文档

| 文档 | 用途 |
|------|------|
| `docs/ARCHITECTURE.md` | 系统架构 |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | 请求管道权威文档 |
| `docs/ROUTING_ENGINE_DESIGN.md` | 路由引擎设计 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` | 设备模型路由指南 |
| `docs/RELEASE_GATE_CHECKLIST.md` | 发布门清单 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 优化路线图 |
