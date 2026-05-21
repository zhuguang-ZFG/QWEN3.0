# LiMa AI 项目状态

> 更新时间: 2026-05-21 (全量审计后)
> 阶段: V3 本地就绪，生产未部署，多项设计未闭环

---

## 当前架构状态

### V3 路由引擎（Phase 1-3 完成，Phase 4 未执行）

| 模块 | 行数 | 状态 | 接入情况 |
|------|------|------|----------|
| routing_engine.py | 226 | ✅ 完成 | server.py 已接入 (LIMA_V3=1) |
| router_v3.py | 225 | ✅ 完成 | routing_engine 内部使用 |
| http_caller.py | 290 | ✅ 完成 | 统一 HTTP 调用层 |
| health_tracker.py | 119 | ✅ 完成 | 指数退避+质量追踪已实现 |
| streaming.py | 158 | ✅ 完成 | speculative_stream 已接入 |
| skills_injector.py | 205 | ✅ 完成 | 23/23 测试通过 |
| sticky_session.py | 60 | ✅ 完成 | routing_engine 内部使用 |
| key_pool.py | 142 | ✅ 完成 | http_caller 内部使用 |
| semantic_cache.py | 103 | ✅ 完成 | routing_engine 已接入 |
| probe_loop.py | 80 | ✅ 完成 | FastAPI lifespan 自动启动 |
| response_builder.py | 92 | ✅ 完成 | server.py 使用 |
| vision_handler.py | 138 | ✅ 完成 | 脱离 smart_router 依赖 |
| tool_handler.py | 145 | ✅ 完成 | _record_request 桩未注入 |
| backends.py | 109 | ✅ 完成 | 117 后端配置 |
| budget_manager.py | — | ✅ 完成 | routing_engine 已接入 |
| identity_guard.py | — | ✅ 完成 | routing_engine 已接入 |
| speculative.py | — | ✅ 完成 | 投机并行执行 |

### 未接入的孤立模块

| 模块 | 状态 | 问题 |
|------|------|------|
| fallback_chain.py | ❌ 死代码 | 4个公开函数零调用点 |
| stats_collector.py | ❌ 死代码 | 完整实现但 server.py 未 import |
| quota_tracker.py | ❌ 死代码 | 与 budget_manager 功能重叠 |
| health_probe.py | ❌ 死代码 | 与 probe_loop.py 重叠，未启动 |
| v3_integration.py | ❌ 待删除 | 被 routing_engine.py 完全覆盖 |

### 遗留依赖（smart_router 退役阻塞）

| 文件 | smart_router 依赖 | 迁移难度 |
|------|-------------------|----------|
| server.py | 24 个属性（常量+函数） | HIGH |
| orchestrate.py | analyze/call_api/route | MEDIUM |

---

## 安全隐患

| 问题 | 位置 | 状态 |
|------|------|------|
| 生产密码明文 `PASS = "zhuguang110!"` | deploy_v3.py:16 | ❌ 未修复 |
| 密码暴露在文档中 | docs/PLATFORM_FIX_PLAN.md:24 | ❌ 未修复 |
| 无任何限流保护 | server.py 全局 | ❌ rate_limiter.py 不存在 |

---

## 工程基础设施

| 项目 | 状态 |
|------|------|
| 服务器依赖清单 (requirements_server.txt) | ❌ 不存在 |
| .env.example 完整性 | ⚠️ 缺 LONGCAT_URL/LONGCAT_MODEL/GPT_API_KEY |
| CI/CD | ❌ 无 |
| 测试覆盖率工具 | ❌ 无 coverage 配置 |
| 主要模块测试 | ❌ server/smart_router/orchestrate/speculative/identity_guard 零测试 |

---

## 设计文档实现状态

| 设计文档 | 核心功能 | 实现状态 |
|----------|----------|----------|
| BACKEND_STABILITY_DESIGN.md | 指数退避 + 质量追踪 | ✅ 已实现 |
| BACKEND_STABILITY_DESIGN.md | 预算管理 | ✅ 已实现 (budget_manager.py) |
| CLAUDE_CODE_BREAKTHROUGH.md | fragments/ + assemble_prompt | ✅ Step 1 完成 |
| CLAUDE_CODE_BREAKTHROUGH.md | prompt缓存/双模式/SafetyMonitor | ❌ Steps 2-6 未实现 |
| DUAL_TRACK_ROUTING_PLAN.md | classify_scenario + 双池 | ❌ 完全未实现 |
| PLATFORM_FIX_PLAN.md | 三层限流 | ❌ 完全未实现 |
| PAYMENT_DESIGN.md | 支付网关 | ❌ 阻塞（需企业资质） |
| STREAMING_REFACTOR_PLAN.md | 流式完全提取 | ⚠️ 部分完成 |
| V3_MIGRATION_PLAN.md Phase 4 | 清理+安全 | ❌ 未执行 |
| LOCAL_MODEL_DESIGN.md | 本地模型 | ⚠️ 实现偏移(Ollama替代LM Studio) |
| LATENCY_OPTIMIZATION.md P2 | vLLM + 路由缓存 | ❌ 未开始 |

---

## 生产环境

| 项目 | 状态 |
|------|------|
| V3 模块部署 | ❌ 服务器仍跑旧版 |
| 开放平台 Channel 端口 | ❌ 8090→8080 未修，平台不可用 |
| systemd 自启 | ❌ 未配置 |
| 数据库备份 | ❌ 无 cron |
| NextChat (chat.donglicao.com) | ❌ 未部署 |
| DNS chat A 记录 | ❌ 未添加 |

---

## Git 状态

| 项目 | 状态 |
|------|------|
| 63 个 training data 文件 staged 为 deleted | ⚠️ 未 commit |
| 未跟踪文件散落 | ⚠️ _stream_test.py, _tcf2.py 等 |
| 当前分支 master vs 主分支 main | ⚠️ 未合并 |
| 断裂引用 train_router_model.py → context_feature_extractor | ❌ 运行即崩 |

---

## 后端总览

117 个后端，24 供应商。主力: LongCat(5), Groq(6), NVIDIA(6), OpenRouter(10), TheOldLLM(12), SCNet(5), CF Workers AI(4)。

---

## 测试覆盖

| 测试文件 | 测试数 | 覆盖模块 |
|----------|--------|----------|
| test_http_caller.py | 27 | http_caller |
| test_skills_injector.py | 23 | skills_injector |
| test_routing_engine.py | 16 | routing_engine |
| test_v3.py | 5 | router_v3 |
| test_streaming.py | 0 | ⚠️ 非 pytest 格式，模块级 HTTP 调用 |
