# LiMa 项目开发规范

## Superpowers 原则

### 1. 文档先行
- 任何非 trivial 改动，先写设计文档再编码
- 文档是设计决策的永久记录，代码会变但决策原因不该丢失
- 参考开源项目时记录具体借鉴了什么，为什么

### 2. 文件小而专注
- 单文件不超过 300 行（含注释）
- 每个文件只做一件事：路由/健康检查/会话管理 分别独立
- 函数不超过 50 行，超过就拆
- 不利于维护的大文件必须拆分

### 3. 本地验证再部署
- 本地完全实现 + 测试通过后，一次性替换服务器文件
- 不在生产服务器上边改边调
- 部署前备份，部署后验证

### 4. 永不破坏生产
- 服务器改动必须可回滚
- 新模块独立文件，不修改核心文件直到确认无误
- 端口冲突/进程残留等问题在部署脚本里处理

### 5. 参考业界最佳实践
- 每个设计决策都应有开源参考佐证
- clone 参考项目，分析源码，提取核心实现
- 不重复造轮子（如 pybreaker 代替自研熔断器）

### 6. 渐进式替换
- 新旧系统并行运行，逐步切流
- 保留旧代码直到新代码完全验证
- 灰度发布：先 1% 流量验证再全量

## 项目结构

```
D:/GIT/
├── server.py              2027行  FastAPI入口（待继续拆分，目标<800行）
├── smart_router.py        1944行  旧路由引擎（待瘦身至<500行）
│
│  ── V3 路由核心（已接入 server.py）──
├── routing_engine.py      226行  五层统一路由 ✅
├── router_v3.py           225行  三层路由+P2C ✅
├── http_caller.py         290行  统一HTTP调用 ✅
├── streaming.py           158行  投机流式 ✅
├── health_tracker.py      119行  指数退避+质量追踪 ✅
├── sticky_session.py       60行  会话亲和 ✅
├── key_pool.py            142行  SWRR轮转 ✅
├── semantic_cache.py      103行  SHA-256缓存 ✅
├── probe_loop.py           80行  主动探活 ✅
├── skills_injector.py     205行  智能补缺 ✅
├── budget_manager.py       —行  预算管理 ✅
├── identity_guard.py       —行  身份拦截 ✅
├── speculative.py          —行  投机并行 ✅
│
│  ── 辅助模块 ──
├── response_builder.py     92行  响应格式 ✅
├── vision_handler.py      138行  视觉路由 ✅
├── tool_handler.py        145行  工具转发（_record_request桩未注入）
├── backends.py            109行  117后端配置 ✅
├── orchestrate.py          —行  多步编排（仍依赖smart_router）
├── voice_gateway.py        —行  WebSocket语音（独立运行）
│
│  ── 待清理/决策 ──
├── v3_integration.py      111行  ❌ 待删除（被routing_engine覆盖）
├── fallback_chain.py       69行  ❌ 死代码（4函数零调用）
├── stats_collector.py     147行  ❌ 死代码（未import）
├── quota_tracker.py        —行  ❌ 死代码（与budget_manager重叠）
├── health_probe.py         —行  ❌ 死代码（与probe_loop重叠）
│
│  ── 部署 ──
├── deploy_v3.py            91行  ⚠️ 含明文密码，待修复
├── patch_server_v3.py     135行  服务器patch
│
│  ── 测试 ──
├── test_http_caller.py     27 tests ✅
├── test_skills_injector.py 23 tests ✅
├── test_routing_engine.py  16 tests ✅
├── test_v3.py              5 tests ✅
├── test_streaming.py       ⚠️ 非pytest格式
│
│  ── 资源 ──
├── skills/                 6个skill文件
├── fragments/              4个prompt片段
├── docs/                   38份设计文档
└── QWEN3.0/                4份逆向分析文档
```

## 开发流程

```
1. 设计文档 (docs/*.md)
2. 本地编码 (D:/GIT/*.py)
3. 本地测试 (pytest / curl)
4. Code Review
5. 一次性部署到服务器
6. 验证 (curl + 真实 IDE 测试)
7. 更新 STATUS.md
```

## 技术栈

- Python 3.10 + FastAPI + uvicorn
- httpx.AsyncClient (替换 urllib)
- pybreaker (熔断器)
- Redis (未来分布式状态)

## 关键设计文档

| 文档 | 内容 | 实现状态 |
|------|------|----------|
| `docs/ROUTING_V3_DESIGN.md` | V3 功能设计 (8模块) | ✅ 已实现 |
| `docs/ROUTING_FIX_PLAN.md` | 14模块实现方案 | ✅ Phase 1-3 完成 |
| `docs/ROUTING_ENGINE_DESIGN.md` | 五层统一路由设计 | ✅ 已实现 |
| `docs/SKILLS_INJECTION_DESIGN.md` | Skills智能补缺 | ✅ 已实现 |
| `docs/BACKEND_STABILITY_DESIGN.md` | 指数退避+质量追踪 | ✅ 已实现 |
| `docs/V3_MIGRATION_PLAN.md` | 迁移4阶段 | ⚠️ Phase 4 未执行 |
| `docs/STREAMING_REFACTOR_PLAN.md` | 流式拆分 | ⚠️ 部分完成 |
| `docs/DUAL_TRACK_ROUTING_PLAN.md` | 编程/聊天双轨 | ❌ 未实现 |
| `docs/PLATFORM_FIX_PLAN.md` | 开放平台修复 | ❌ P0未修 |
| `docs/LATENCY_OPTIMIZATION.md` | 延迟优化 | ⚠️ P0-P1完成, P2未开始 |
| `docs/CLAUDE_CODE_BREAKTHROUGH.md` | Prompt工程5步 | ⚠️ 仅Step1完成 |
| `docs/PAYMENT_DESIGN.md` | 支付网关 | ❌ 阻塞(需企业资质) |
| `docs/LOCAL_MODEL_DESIGN.md` | 本地模型 | ⚠️ 实现偏移(Ollama) |
| `STATUS.md` | 项目状态追踪 | — |
| `docs/EXECUTION_PLAN.md` | 执行计划(本文档) | 📋 当前 |
