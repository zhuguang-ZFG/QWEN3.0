# LiMa Status

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com, api.donglicao.com
> **部署**: Alibaba Cloud VPS + JDCloud 备用

> Updated: 2026-06-15
> Branch: `design/route-policy-backend-field`
> Tests: **2009+ tests** (185 in focused device+routing+ops suite); ruff clean; pre-commit passing
> Quality: P0 violations resolved; legacy routing/HTTP stack retired

## 当前项目状态

### 核心功能
- **设备网关**: ESP32 绘图机/写字机云端控制
- **AI 路由**: 170+ 后端智能路由（设备任务 + 聊天/编码）
- **任务管理**: 任务创建、派发、执行、监控
- **设备策略**: 安全策略、固件兼容性、路径验证

### 最近完成（2026-06-15）
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
- **文档归档中**：`task_plan.md`（旧个人编码助手计划）部分条目已过时，`docs/README.md` 已标注其历史定位
- **本地/远程双环境**：Windows 本地代理后端、FRP `:8088`、VPS 直接后端共存，新增后端需明确拓扑归属

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
| `docs/ROUTING_ENGINE_DESIGN.md` | 路由引擎设计 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由指南 |
| `docs/RELEASE_GATE_CHECKLIST.md` | 发布门清单 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 优化路线图 |
