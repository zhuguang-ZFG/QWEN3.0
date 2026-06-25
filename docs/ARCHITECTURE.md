# LiMa 系统架构文档

## 1. 系统概述

LiMa 是深圳市动力巢科技有限公司（donglicao.com）面向 ESP32 绘图机/写字机/2D 数字人的 AI 智能设备统一云端服务平台。

核心使命：让每个家庭拥有会画画、会写字的智能伙伴。

当前版本：`lima-1.3`，Python 3.10 + FastAPI，生产入口为 `server.py`，公共服务域名为 `chat.donglicao.com`。

## 2. 架构全景图

```text
┌──────────────────────────────────────────────────────────────┐
│ 客户端层                                                     │
│ 小程序 / App / Web 控制台                                    │
└───────────────┬───────────────────────────────┬──────────────┘
                │ HTTPS                         │ WebSocket
                ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│ API 层：FastAPI routes/                                      │
│ - Chat API：routes/chat_endpoints.py                         │
│ - Device Gateway：routes/device_gateway.py                   │
│ - Task Queue：device_gateway/tasks.py + store/redis_store.py │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 业务层                                                       │
│ - AI Router：routing_engine.py / router_v3/ 包 / selector     │
│ - Drawing Engine：自然语言 → SVG → 路径优化 → G-code          │
│ - Writing Engine：device_gateway/path_pipeline.py 文本渲染    │
│ - Voiceprint Service：v2_voiceprint 数据模型                 │
│ - Device Manager：绑定、状态、任务、RMA、耗材、自检            │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 基础设施层                                                   │
│ SQLite / Redis / MQTT / Prometheus / Grafana                 │
│ migrations/xiaozhi_schema.sql                                │
│ observability/prometheus_*.py                                │
└───────────────┬──────────────────────────────────────────────┘
                │ MQTT / WebSocket
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 设备层                                                       │
│ ESP32 绘图机 / 写字机 ← MQTT                                 │
└──────────────────────────────────────────────────────────────┘
```

## 3. 核心模块说明

### routes/ — API 路由层
`routes/` 是 FastAPI 路由注册层，由 `routes/route_registry.py` 统一挂载。当前已注册 `chat_endpoints`、`device_gateway`、`device_app_*`、`device_ota`、`device_ota_app`、`admin`、`admin_v1_auth`、`system_endpoints`、`ops_metrics`、`fleet`、`eval_internal`、`xiaozhi_compat`（默认关闭）等路由。

### xiaozhi-v1 兼容层（已退役）
`routes/xiaozhi_compat/` 兼容层已于 2026-06-26 物理删除。原 `/api/v1/*` 端点已由 LiMa 原生管理面 `/device/v1/app/*`（`routes/device_app_*.py`）完全替代，覆盖账号、设备、成员、任务、素材、通知、统计等能力。

数据层由 `migrations/xiaozhi_schema.sql` 提供 SQLite schema。

### device_gateway/ — 设备网关
`device_gateway/` 负责设备协议、任务投递、会话管理和 MQTT/WebSocket 通信。`routes/device_gateway.py` 暴露 `/device/v1` 前缀的设备健康、事件、任务和 WebSocket 入口。

### routing_engine.py — AI 路由
AI 路由入口，负责身份短路由、请求分类、场景分类、检索上下文注入、后端选择、技能注入、推测调用、执行与结果封装。后端池来自 `backends_registry/` 与 `router_v3/` 包，支持 170+ 后端调度、健康检查和熔断。

### device_logic/ — 设备与账号逻辑
`device_logic/` 承载账号、鉴权、API Key、设备绑定/成员/转移/耗材/自检、任务统计等核心业务逻辑，被 `routes/device_app_*.py`、`routes/device_gateway*.py` 与 `routes/admin*.py` 复用。

### device_gateway/ — 设备执行引擎
AI 绘图执行链：`device_gateway/task_draw_params.py` → `device_draw_handler.py`（万相简笔画 + OpenCV 矢量化）→ `path_pipeline.py` / `path_validator.py` / `motion.py` / `safety.py`。自然语言 `draw_generated` 于 2026-06-18 接入主任务创建热路径。`xiaozhi_drawing/` 目录为遗留实验代码，不在当前热路径。

### session_memory/ — 会话记忆
提供长期记忆、结果账本、学习循环、脱敏、压缩和提示召回能力。

### observability/ — 可观测性
负责结构化日志、Prometheus 指标、后端遥测、关联 ID、事件记录和能力证据。

### device_policy/ — 安全策略引擎
`engine.py` 的 `PolicyEngine` 按协议兼容、安全边界和设备能力三道门决策，在任务入库前阻止不安全任务下发。

## 4. 数据架构

Phase 1-2 使用 SQLite（WAL + 外键），核心表已扩展至以下（按业务域分组）：

| 表名 | 作用 |
|---|---|
| `v2_account` | 用户账号 |
| `v2_api_key` | App 自助 API Key |
| `v2_device` | 设备基础信息 |
| `v2_device_binding` | 账号与设备绑定 |
| `v2_member` | 家庭成员 |
| `v2_voiceprint` | 声纹特征数据 |
| `v2_task` | 设备运动任务 |
| `v2_task_template` | 任务模板 |
| `v2_asset` | 素材库 |
| `v2_notification` | 通知订阅与记录 |
| `v2_share` | 设备分享/访客 |
| `v2_device_transfer_request` | 设备转移工单 |
| `v2_device_rma_event` | 维修 RMA 事件 |
| `v2_device_supply` | 耗材状态 |
| `v2_self_check_event` | 自检结果 |

Phase 3+：设备 >500 台 → PostgreSQL。

## 5. 请求处理流水线

### Chat/AI 请求链路
```
Client → server.py → access_guard → chat_endpoints → routing_engine.route()
→ identity_guard → classifier → context_pipeline → selector → executor
→ http_caller → backend → response → chat_post_closeout → Client
```

### 设备任务链路
```
Client → POST /device/v1/tasks → device_gateway → intent.resolve
→ path_pipeline → path_validator → policy_engine.decide()
→ task_store → MQTT/WS downlink → ESP32 → motion_event uplink
→ ledger / observability
```

## 6. 部署架构

双 VPS 高可用：主节点 + JDCloud 备用节点。
`chat.donglicao.com` → Nginx → Docker Compose → lima-router:8080。
部署脚本：`scripts/deploy_unified.py`。

## 7. 安全设计

- JWT 认证用于用户态接口
- 设备绑定校验（v2_device + v2_device_binding）
- MQTT TLS + 设备级 topic 隔离
- API Key 通过环境变量管理

## 8. Phase 演进路线

| Phase | 目标 | 状态 |
|-------|------|------|
| Phase 0 | 战略转型 + 基础设施 | ✅ 完成 |
| Phase 1 | 核心设备服务 + 路由契约 | ✅ 完成 |
| Phase 2 | 按角色准入 AI 绘图/写字模型 | ✅ 完成 |
| Phase 3 | 设备配置文件路由输入 | ✅ 完成 |
| Phase 4 | 通用 LLM 路由加固 | ✅ 完成 |
| Phase 5 | AI 到运动发布门 | ✅ 完成 |
| Phase A/B/C | 官网、文档、SDK、控制台、CI/CD | ✅ 完成 |
