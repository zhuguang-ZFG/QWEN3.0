# LiMa 代码库质量审计报告

**审计日期**: 2026-06-13
**审计范围**: `D:\QWEN3.0` — Python FastAPI 多后端 AI 路由服务器
**审计方法**: 9 领域并行审计（ln-621 ~ ln-629）
**审计结果**: 9/9 全部完成

---

## 执行摘要

| 指标 | 值 |
|------|-----|
| 总发现数 | **118** |
| CRITICAL | **5** |
| HIGH | **32** |
| MEDIUM | **51** |
| LOW | **30** |
| 整体评分 | **C+**（有严重问题需立即修复） |

**最紧急的 3 个问题**：
1. `backends_registry.py:23` 硬编码生产 API 密钥（已被 git 记录）
2. `budget_manager.py:172` `Lock` 非 `RLock` 嵌套调用**必定死锁**
3. `check_qwen_status.py:6` 包含明文 VPS 密码

---

## 一、安全边界审计（ln-621）— 2C / 4H / 5M / 3L

### CRITICAL

| # | 文件 | 问题 |
|---|------|------|
| S-C1 | `backends_registry.py:23` | 生产 API 密钥 `sk-XUgLWn...` 硬编码为 `os.environ.get()` 的 fallback 默认值 |
| S-C2 | `test_sharedchat.py:5` + 3 个测试文件 | 4 个测试文件包含明文 API 密钥 |

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| S-H1 | `routing_loop/request_store.py:183` | `pickle.loads()` 反序列化 SQLite 数据，可被注入恶意 payload |
| S-H2 | `routes/admin_api.py:212` | `/api/retrain` 端点执行 `subprocess.run`，admin session cookie 无过期 |
| S-H3 | `tool_gateway/executor.py:111` | `_exec_shell()` 模板字符串未验证，存在命令注入风险 |
| S-H4 | `sandbox/provider.py:181` | `FakeSandboxProvider` 接受任意命令，无命令白名单 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| S-M1 | 7 个文件 | SQL 查询通过 f-string 构造（结构部分，非参数值） |
| S-M2 | `tmp_explore_db.py:22` | 临时脚本中不受限的 SQL 执行 |
| S-M3 | `server.py:47` | Sentry `send_default_pii=True` 泄露用户数据 |
| S-M4 | `routes/admin_auth.py:20-35` | Admin session cookie 无过期，被盗即永久有效 |
| S-M5 | `server.py` | 公开端点无速率限制 |

### LOW

| # | 文件 | 问题 |
|---|------|------|
| S-L1 | `server.py:35` | OpenAPI/Swagger 文档公开暴露 |
| S-L2 | `routes/chat_endpoints.py` | 消息内容无长度/字符验证 |
| S-L3 | `backends_registry.py:7-15` | 硬编码 localhost URL |

---

## 二、构建交付门禁审计（ln-622）— 3H / 1M / 4L

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| B-H1 | 3 个测试文件 | `needs_orchestration` 已迁移到 `orchestrate.py`，monkeypatch 目标过期导致 3 个测试失败 |
| B-H2 | 项目全局 | **547 个文件**未通过 `ruff format --check`，格式化债务巨大 |
| B-H3 | `.github/workflows/test.yml` | CI 缺少 `ruff format --check` 门禁 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| B-M1 | `.github/workflows/test.yml` | CI 无覆盖率阈值门禁 |

### LOW

| # | 文件 | 问题 |
|---|------|------|
| B-L1 | 3 个测试文件 | Skip 原因字符串过期（"not yet implemented" → 实际已移除） |
| B-L2 | 测试文件 | JWT 测试密钥长度不足 32 字节 |
| B-L3 | `.github/workflows/test.yml:43` | CI 忽略 5 个测试文件但未文档化 |
| B-L4 | `.github/workflows/deploy.yml` | CI 部署绕过 `deploy_unified.py` 的回滚安全网 |

---

## 三、并发正确性审计（ln-628）— 5H / 9M / 2L

### HIGH（真实死锁/阻塞）

| # | 文件 | 问题 |
|---|------|------|
| C-H1 | `budget_manager.py:172` | `_lock` 是 `Lock()` 而非 `RLock()`，`get_all_budgets()` 内部调用 `get_budget_status()` **必定死锁** |
| C-H2 | `speculative.py:59` | `_run_coro_sync()` 在 async 路径中 `thread.join()` 阻塞 event loop |
| C-H3 | `health_scoring.py:60` | `get_scores()` 锁释放后逐个 `compute_score()`，快照非原子 |
| C-H4 | `session_memory/store_db.py:55` | 每次 CRUD 操作创建新 SQLite 连接，无连接池 |
| C-H5 | `routes/admin_api.py:205` | `asyncio.create_task` fire-and-forget 无错误处理，任务异常被静默丢弃 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| C-M1 | `routing_executor.py:170` | `ThreadPoolExecutor` 阻塞 async event loop |
| C-M2 | `backend_profile.py:233` | `load_profiles()` 无锁写入全局字典 |
| C-M3 | `key_pool.py:143` | `_pools` 全局字典无锁保护 |
| C-M4 | `health_state.py:190` | 持锁期间执行完整 SQLite I/O 周期 |
| C-M5 | `session_memory/daemon.py:270` | 非原子读-删-写操作 |
| C-M6 | `session_memory/daemon.py:62` | daemon 异常导致静默终止 |
| C-M7 | `context_pipeline/ensemble.py:79` | 并行任务无取消处理 |
| C-M8 | `routing_engine.py:191` | 冷却检查与执行非原子（TOCTOU） |
| C-M9 | `session_memory/daemon.py:26` | `_stats` 全局字典无锁写入 |

### LOW

| # | 文件 | 问题 |
|---|------|------|
| C-L1 | `routing_engine.py:228` | sticky session 可能 pin 到已 cooldown 后端 |
| C-L2 | `health_recorder.py` + `backend_profile.py` | 跨模块锁获取顺序未文档化 |

---

## 四、可维护性热点审计（ln-624）— 1C / 3H / 5M

### CRITICAL

| # | 文件 | 问题 |
|---|------|------|
| M-C1 | `routing_engine.py:77` | `route()` 函数：**235 行、13 参数、8 层嵌套、19 个 if 分支、82 次函数调用** — 整个项目最大的可维护性风险 |

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| M-H1 | `routing_selector.py:87` | `select()` 184 行、7 参数、4 层嵌套 |
| M-H2 | `routes/route_registry.py:51` | `register_all_routes()` 188 行、33 个 import |
| M-H3 | `router_v3.py:190` + `routing_classifier.py:85` | `_has_image_blocks()` 在两个文件中重复定义 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| M-M1 | 4 个模块 | 超时常量不一致：5s / 15s / 30s / 60s 散布各处 |
| M-M2 | `routing_engine.py` + `router_v3.py` | `request_type` / `req_type` 标识符漂移 |
| M-M3 | `streaming.py:82` | `speculative_stream()` 10 个参数 |
| M-M4 | `backends_registry.py` | ~202 个后端条目使用内联魔术数字超时 |
| M-M5 | `channel_gateway/service.py` | 567 行上帝模块 |

---

## 五、死代码审计（ln-626）— ~1,186 行可回收

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| D-H1 | `check_qwen_status.py:6` | **包含明文 VPS 密码** `XINdandan521!` — 立即删除并轮换密码 |
| D-H2 | 12 个 tmp/debug/check 脚本 | 一次性脚本应删除 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| D-M1 | `device_memory/` 4 个文件 | 占位模块（3 行，无实现） |
| D-M2 | `smart_router.py` + `router_http*.py` | 5 个遗留 facade 模块仍被 6 个生产路由模块导入 |
| D-M3 | 18 处 | 生产代码中未使用的 import |

---

## 六、依赖与复用审计（ln-625）— 5H / 8M

### HIGH

| # | 问题 |
|---|------|
| D-H1 | `alembic`, `pypotrace`, `svgpathtools`, `shapely` 是死依赖 — 仅在 `scripts/verify_drawing_deps.py` 中导入 |
| D-H2 | `tree-sitter-languages` 在 `code_context/treesitter_adapter.py:82` 中使用但未列入 requirements |
| D-H3 | `chromadb` 可选依赖未文档化 |

### MEDIUM

| # | 问题 |
|---|------|
| D-M1 | 三个 HTTP 客户端库共存：httpx（75 imports）、urllib.request（97 imports）、requests（33 imports） |
| D-M2 | `uvicorn`, `httpx`, `redis` 无版本上限 |
| D-M3 | `hypothesis`, `pyright`, `deptry` 开发依赖混在运行时 requirements 中 |
| D-M4 | 绘图引擎依赖（numpy, opencv）~60MB 仅用于 1 个模块，应设为可选 |
| D-M5 | `paramiko` 是部署工具依赖，不应在运行时 requirements 中 |

---

## 七、运行时生命周期审计（ln-629）— 1C / 3H / 3M / 6L

### CRITICAL

| # | 文件 | 问题 |
|---|------|------|
| R-C1 | `backends_registry.py:23` | 硬编码生产 API 密钥（与 S-C1 重复） |

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| R-H1 | `routes/system_endpoints.py:50` | `/health` 端点返回静态 "ok"，不检查任何子系统 |
| R-H2 | `access_guard.py:40` | `LIMA_API_KEY` 未在启动时验证 — 服务器启动正常但所有端点返回 503 |
| R-H3 | `.env.example` | `LIMA_API_KEY` 未记录在 `.env.example` 中 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| R-M1 | `routes/system_endpoints.py:49` | 无 readiness/liveness 分离 |
| R-M2 | `server.py:11` | dotenv ImportError 静默吞没 |
| R-M3 | `.env.example` | ~50 个 `LIMA_*` 环境变量未文档化 |

---

## 八、可诊断性审计（ln-627）— 1H / 4M

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| G-H1 | 多个文件（30+ 处） | ~30 个裸 `except Exception:` 块无日志记录，静默吞没异常 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| G-M1 | `observability/structured_logging.py:15` | 结构化日志默认关闭（`LIMA_STRUCTURED_LOGGING=0`） |
| G-M2 | `context_pipeline/tracing.py` | `chat_id`（客户端可见）与 `trace_id`（内部追踪）未关联 |
| G-M3 | `health_failure_classifier.py` + `backend_telemetry.py` | 两套重叠但不同的错误分类系统 |
| G-M4 | `observability/correlation.py` | 关联环形缓冲区仅内存存储（500 事件），重启丢失 |

---

## 九、重复/过度抽象审计（ln-623）— 8H / 13M / 8L

### HIGH

| # | 文件 | 问题 |
|---|------|------|
| X-H1 | `router_circuit_breaker.py` + `health_state.py` | 两套熔断系统同时生效：旧版 3 态 + V3 指数退避 |
| X-H2 | `routing_executor.py` + `routes/chat_fallback.py` | 两套并行回退引擎功能重叠 |
| X-H3 | `routes/v3_adapters.py:31-265` | 6x 复制粘贴上下文注入模式（~120 行冗余） |
| X-H4 | `backends_registry.py` vs `backends_registry/commercial.py` | ≥15 个后端条目在两处重复定义 |
| X-H5 | `smart_router.py`（227 行） | 纯向后兼容 facade，4 个生产文件死导入 |
| X-H6 | `router_http.py`（161 行） | 仅剩 1 个生产调用者，已被 `http_caller` 完全替代 |
| X-H7 | `search_gateway/codesearch_status.py` + 3 文件 | 4 个死代码函数（零调用者） |
| X-H8 | `backends_registry/__init__.py:50` | `DISABLED_HOST_DEPENDENT_BACKENDS` 空字典，从未使用 |

### MEDIUM

| # | 文件 | 问题 |
|---|------|------|
| X-M1 | 23 个文件 | 各自重复实现 `env_truthy()` 而非使用 `runtime_topology.env_truthy()` |
| X-M2 | 9 个文件 | Anthropic auth header 构造重复 9 处 |
| X-M3 | `http_stream.py` | 同步/异步流错误处理复制粘贴 |
| X-M4 | 25 处 | `isinstance(body, JSONResponse)` 样板代码 |
| X-M5 | `routes/github_webhook.py` + `gitee_webhook.py` | Webhook 配置助手函数 4 个重复 |
| X-M6 | `routes/ops_metrics.py` | ImportError+503 / Exception+500 模式重复 5 次 |
| X-M7 | 3 个文件 | 单实现 ABC（`SandboxProvider`, `LocalRetrievalIndex`, `VectorIndex`） |
| X-M8 | 2 个文件 | 重复 ABC 定义（`GraphIndex`, `DevSearchAdapter`） |
| X-M9 | `routes/token_sync.py` + `routes/admin_backends.py` | Token 验证探测重复 |
| X-M10 | `smart_router.py:51-65` | `ROUTE` 字典（14 条目）仅用于 `/v1/status` 元数据 |
| X-M11 | `scripts/test_route_e2e.py:13` | 导入不存在的 `route` 和 `ONEAPI_ENABLED` — 脚本已损坏 |
| X-M12 | `auto_retrain.py:264-268` | 直接修改 `smart_router` 内部状态 |
| X-M13 | `smart_router.py` | 4 个生产文件死导入 `smart_router` |

### LOW

| # | 文件 | 问题 |
|---|------|------|
| X-L1 | 4 处 | `MODEL_ID` 字符串在 4 个文件中重复 |
| X-L2 | 3 处 | `LM_URL` 在 3 个文件中重复 |
| X-L3 | 16 个 `__init__.py` | 纯重导出 facade（标准 Python 实践，可接受） |
| X-L4 | `backends.py` | 薄重导出 facade |
| X-L5 | 15 个文件 | `load_dotenv()` 重复调用（幂等，低风险） |
| X-L6 | 4 个工厂函数 | 仅测试使用的工厂函数 |
| X-L7 | `esp32S_XYZ/` | 硬编码 feature flag 永远为 True |
| X-L8 | `provider_automation/` | 测试专用工厂函数 |

---

## 去重说明

以下发现在多个审计中被独立发现，合并计为 1 项：

| 发现 | 出现审计 |
|------|----------|
| `backends_registry.py:23` 硬编码 API 密钥 | ln-621, ln-629 |
| `check_qwen_status.py` 明文 VPS 密码 | ln-621, ln-626 |
| `except ImportError: pass` 静默降级 | ln-627, ln-629 |
| SQLite 连接管理问题 | ln-628, ln-629 |
| 遗留 facade 模块仍被使用 | ln-625, ln-626, ln-623 |
| 两套熔断系统共存 | ln-623, ln-628 |

---

## 优先修复计划

### P0 — 立即修复（阻塞级）

| 序号 | 问题 | 影响 | 工作量 | 修复方案 |
|------|------|------|--------|----------|
| 1 | 硬编码 API 密钥 (`backends_registry.py:23`) | 安全 | 5min | 删除 fallback 默认值，轮换密钥 |
| 2 | 明文 VPS 密码 (`check_qwen_status.py:6`) | 安全 | 2min | 删除文件，轮换 VPS 密码 |
| 3 | 测试文件明文 API 密钥 (4 文件) | 安全 | 15min | 改用 env var，轮换密钥 |
| 4 | `budget_manager` 死锁 (`_lock` 非 RLock) | 可用性 | 2min | `threading.Lock()` → `threading.RLock()` |
| 5 | 3 个测试 monkeypatch 失败 | CI | 10min | 更新 monkeypatch 目标为 `orchestrate` |

### P1 — 本周修复（高影响）

| 序号 | 问题 | 影响 | 工作量 | 修复方案 |
|------|------|------|--------|----------|
| 6 | `pickle.loads` 反序列化 | 安全 | 30min | 改用 JSON 序列化 |
| 7 | Admin session cookie 无过期 | 安全 | 1h | 添加时间戳到 HMAC，24h 过期 |
| 8 | 547 文件格式化债务 | 代码质量 | 30min | 运行 `ruff format .` |
| 9 | CI 缺少 format check 门禁 | CI | 5min | 添加 `ruff format --check` |
| 10 | `LIMA_API_KEY` 启动验证 | 运维 | 15min | 在 `server_lifespan.py` 添加启动检查 |
| 11 | `/health` 静态 "ok" | 可靠性 | 30min | 添加子系统健康检查 |
| 12 | `speculative.py` 阻塞 event loop | 性能 | 2h | 重构为 async-first |
| 13 | 30+ 裸 `except Exception:` 无日志 | 可诊断性 | 1h | 添加 `logger.debug(exc_info=True)` |

### P2 — 本月修复（中等影响）

| 序号 | 问题 | 影响 | 工作量 |
|------|------|------|--------|
| 14 | `routing_engine.route()` 拆分 | 可维护性 | 4h |
| 15 | HTTP 客户端统一（urllib→httpx） | 一致性 | 4h |
| 16 | 死依赖清理（alembic, pypotrace 等） | 依赖 | 30min |
| 17 | 死代码删除（12 个 tmp 脚本 + placeholder） | 代码质量 | 30min |
| 18 | 结构化日志默认启用 | 可诊断性 | 1h |
| 19 | `.env.example` 补全文档 | 运维 | 1h |
| 20 | SQLite 连接池（session_memory） | 性能 | 2h |
| 21 | Sentry PII 关闭 | 安全 | 5min |
| 22 | `v3_adapters.py` 6x 上下文注入去重 | 代码质量 | 2h |
| 23 | 23 个文件采用 `env_truthy()` | 一致性 | 1h |
| 24 | 两套熔断系统合并 | 架构 | 4h |
| 25 | `router_http.py` 最后调用者迁移 | 遗留清理 | 1h |
| 26 | 4 个死代码函数删除 | 代码质量 | 15min |

---

## 积极发现（做得好的地方）

- ✅ `access_guard.py` 使用 `secrets.compare_digest` 防时序攻击
- ✅ Admin auth 使用 HMAC + 常量时间比较
- ✅ CSRF 保护覆盖所有 admin 变更端点
- ✅ 路径遍历保护正确实现（`sandbox/provider.py`, `lima_mcp/fs_allowlist.py`）
- ✅ 事件系统全面脱敏（`observability/events.py`）
- ✅ 工具网关参数正则验证
- ✅ Prometheus 指标覆盖全面（7 种指标类型）
- ✅ `/v1/ops/` 诊断端点体系完善（关联、指标、后端生命周期管理）

---

**审计完成** | 报告路径: `CODEBASE_AUDIT_2026-06-13.md`
