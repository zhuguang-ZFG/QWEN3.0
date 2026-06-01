# LiMa 产品定义

> 2026-06-01 · 基于 `docs/REQUEST_PIPELINE_AUTHORITY.md` 权威边界文档

## 一、LiMa 是什么

**LiMa 是一个个人 AI 编程助手平台**，由两部分组成：

| 组件 | 角色 | 部署位置 |
|------|------|----------|
| **LiMa Server** | 多模型路由网关 + Agent 运行时 + 会话记忆 | VPS |
| **LiMa Code CLI** | 终端交互式编码助手 | 用户本机 |

## 二、请求管线（权威架构）

来自 `docs/REQUEST_PIPELINE_AUTHORITY.md`（唯一权威来源）：

```
Client → server.py → chat_endpoints → chat_preflight
  → routing_engine.route() [权威路由]
  → http_caller [HTTP 传输]
  → route_post_process + response_cleaner [后处理]
  → chat_post_closeout [记忆+指标]
```

### 模块职责矩阵

| 关注点 | 权威模块 | 备注 |
|--------|----------|------|
| 后端注册 | `backends_registry.py` | 184 个后端，全部云端化 |
| 意图+复杂度分类 | `routing_engine.py` | smart_router 是兼容层，delegates or mirrors |
| 后端选择+fallback | `routing_engine.py` | router_v3 提供 P2C/sticky 补充 |
| 健康/冷却 | `health_tracker.py` | 优于 circuit_breaker |
| HTTP 调用 | `http_caller.py` | httpx；旧 urllib 路径待迁移 |
| 流式桥接 | `streaming.py` | 工具原生 vs 模拟 SSE |
| 检索注入 | `routing_engine` + `local_retrieval` | |
| 技能注入 | `skills_injector.py` | 温度门控 |
| 语义缓存 | `semantic_cache.py` | temperature=0 only |
| 会话记忆 | `session_memory/` | SQLite，db/crud/promote/admin 已拆分 |
| 质量重试 | `routes/quality_gate*.py` | 与根 quality_gate.py 功能不同 |
| Agent 任务 | `routes/agent_tasks.py` | 不在聊天热路径 |
| 预算 | `budget_manager.py` | 从 routing_engine 接入 |

## 三、不在权威路径上的模块

| 模块 | 状态 | 说明 |
|------|------|------|
| `smart_router.py` | 兼容层 | 26 个调用方，urllib 栈，本地 Qwen3 路由模型。功能被 routing_engine 覆盖 |
| `router_http.py` | 旧 HTTP 栈 | urllib，应迁移到 http_caller |
| `router_circuit_breaker.py` | 旧熔断 | health_tracker 已取代 |
| `router_intent.py` / `router_classifier.py` / `router_prompt.py` | 已提取 | CQ-014 从 smart_router 拆分 |
| `context_pipeline.factory` | 实验 | lab/test harness only |

## 四、核心体验

用户通过 CLI 或 IDE 发起编程任务 → LiMa Server 自动选择最优免费模型 → 返回结果。

## 五、目标用户与边界

- **目标**：个人开发者（owner 本人），Python 后端为主
- **不做**：开放平台、模型训练、托管服务、MCP 市场、IoT、多语言 i18n、Web 管理面板、付费/多租户
- **后端原则**：已有 184 个，重点转向质量和延迟，新后端需 eval 数据

## 六、当前项目状态（2026-06-01）

- M1-M7 完成：全部 184 后端云端化，LOCAL_ONLY_BACKENDS 清空
- M8-M9 完成：MiMo-Reasonix 分析 + LiMa Code CLI 初始化
- M10 完成：文档更新
- M11a-f 完成：ModelScope 集成 + ContextManager 移植 + 代码审查
- VPS 验证通过：5 个 sidecar active，FRP/duckai/proxy 已清理
- 测试：LiMa 1972 pass，CLI 498 pass

## 七、待办（按优先级）

| 优先级 | 任务 | 依据 |
|--------|------|------|
| P0 | 决定 CLI 策略：继续维护 fork vs MiMo-Reasonix 重写 vs 自研 | 当前 fork 有上游分歧风险 |
| P1 | 处理 ContextManager：完成 SessionManager 集成或删除孤儿代码 | 280 行未集成代码 |
| P2 | 迁移 smart_router 的 26 个调用方到 routing_engine | AUTHORITY doc 明确 routing_engine 是权威 |
| P2 | 迁移 router_http urllib 调用方到 http_caller (httpx) | AUTHORITY doc 明确 http_caller 是权威 |
| P3 | 退役 router_circuit_breaker（health_tracker 已取代） | AUTHORITY doc |
