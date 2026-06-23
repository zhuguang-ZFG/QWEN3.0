# LiMa 项目缺陷分析与改善计划

> 创建时间：2026-06-22
> 分析范围：全项目代码质量、测试覆盖、安全运维、架构设计四维度
> 分析方法：CodeGraph + ripgrep + 代码审查 + 配置分析
> 基线：约 1356 个 Python 文件 / 179,647 行代码 / 2402 passed / 19 skipped

---

## 目录

- [1. 执行摘要](#1-执行摘要)
- [2. 缺陷分级总表](#2-缺陷分级总表)
- [3. P0 — 必须立即修复](#3-p0--必须立即修复)
- [4. P1 — 高优先级修复](#4-p1--高优先级修复)
- [5. P2 — 中优先级修复](#5-p2--中优先级修复)
- [6. P3 — 低优先级改善](#6-p3--低优先级改善)
- [7. 改善路线图与里程碑](#7-改善路线图与里程碑)
- [8. 度量指标与验收标准](#8-度量指标与验收标准)

---

## 1. 执行摘要

本次对 LiMa 项目进行了四维度全面缺陷分析：

| 维度 | 分析范围 | 发现数 |
|------|---------|--------|
| 代码质量与结构 | 尺寸违规、重复代码、模块耦合、死代码、配置一致性 | 15 项 |
| 测试覆盖与质量 | 覆盖空白、flaky 测试、隔离问题、跳过测试、测试质量 | 12 项 |
| 安全与运维 | 静默降级、硬编码密钥、输入验证、HTTP 明文、日志泄露、CORS/CSRF、部署安全、依赖安全 | 14 项 |
| 架构与设计 | 流水线问题、模块职责、接口设计、状态管理、配置管理、错误处理、流水线膨胀、数据层、并发异步 | 18 项 |

**总计 59 项缺陷/改善点**，其中：
- **P0（必须立即修复）**：6 项
- **P1（高优先级）**：12 项
- **P2（中优先级）**：21 项
- **P3（低优先级改善）**：20 项

**关键风险摘要**：
1. `backend_reputation.py` 全局可变状态无线程保护 → 生产环境数据竞争
2. MQTT 客户端在同步回调中使用已弃用的 `asyncio.get_event_loop()` → 无事件循环时崩溃
3. Admin 配置导入端点缺少 URL 安全验证 → 可注入内网/HTTP 后端
4. routing_executor 核心执行路径零测试覆盖 → 降级/并行逻辑无保障
5. 17 处模块级 `os.environ` 赋值不清理 → 并行测试冲突
6. SQLite `check_same_thread=False` 无锁保护 → 数据库损坏风险

---

## 2. 缺陷分级总表

### P0 — 必须立即修复（6 项）

| ID | 维度 | 缺陷 | 文件 | 影响 |
|----|------|------|------|------|
| P0-1 | 架构 | `backend_reputation.py` 全局可变状态无线程保护 | `backend_reputation.py:10-14` | 生产环境数据竞争 |
| P0-2 | 架构 | MQTT 同步回调中使用 `asyncio.get_event_loop()` | `device_gateway/mqtt_client.py:104` | 无事件循环时崩溃 |
| P0-3 | 安全 | Admin 配置导入端点缺少 URL 安全验证 | `routes/admin_extra_config.py:36-46` | 可注入内网/HTTP 后端 |
| P0-4 | 代码质量 | `.gitignore` 缺失 `.test-tmp/`、`.pnpm-store/`、`.venv310/` | `.gitignore` | 误提交大量文件 |
| P0-5 | 代码质量 | 意外空文件 `=6.0` 残留在根目录 | `=6.0` | 仓库卫生 |
| P0-6 | 测试 | `test_external_enrichment.py` 隐藏网络依赖 | `tests/test_external_enrichment.py:56-80` | CI 断网即失败 |

### P1 — 高优先级修复（12 项）

| ID | 维度 | 缺陷 | 文件 | 影响 |
|----|------|------|------|------|
| P1-1 | 架构 | SQLite `check_same_thread=False` 无锁保护 | `code_context/sqlite_graph_store.py:29`, `device_logic/db.py:62` | 数据库损坏 |
| P1-2 | 架构 | 496 处环境变量读取分散在 148 个文件中，无集中配置 | 148 个文件 | 配置不一致 |
| P1-3 | 架构 | `routing_engine_context.py` 延迟导入+异常吞没导致静默降级 | `routing_engine_context.py:10-93` | 用户无感知功能丢失 |
| P1-4 | 架构 | 88 处 `except Exception` 仅 debug log，违反硬规则 #1 | 多个文件 | 静默降级 |
| P1-5 | 测试 | routing_executor 系列模块零测试覆盖 | `routing_executor*.py`（5 模块） | 核心执行路径无保障 |
| P1-6 | 测试 | `device_gateway/auth.py`、`safety.py` 零测试覆盖 | `device_gateway/auth.py`, `safety.py` | 认证/安全核心无测试 |
| P1-7 | 测试 | 17 处模块级 `os.environ` 赋值不清理 | 10 个测试文件 | 并行测试冲突 |
| P1-8 | 代码质量 | 10 份完全相同的 `design_system.py` 副本（~5.5MB） | 10 个 agent 配置目录 | 仓库膨胀 |
| P1-9 | 代码质量 | `context_pipeline/graph_context_expander.py` 等零生产引用 ✅ 已修复 | 4+ 模块 | 死代码 |
| P1-10 | 代码质量 | `context_pipeline/complexity.py` 与 `speculative_policy.classify_complexity` 功能重复 ✅ 已修复 | 2 个模块 | 重复计算+决策不一致 |
| P1-11 | 安全 | 部署脚本通过 HTTP 下载 Prometheus 无完整性校验 ✅ 已修复 | `deploy/jdcloud/deploy_jd.py:19` | MITM 篡改风险 |
| P1-12 | 安全 | `device_logic/auth.py:50` 认证异常静默返回 False | `device_logic/auth.py:50-51` | 掩盖认证系统故障 |

### P2 — 中优先级修复（21 项）

| ID | 维度 | 缺陷 | 文件 | 影响 |
|----|------|------|------|------|
| P2-1 | 代码质量 | 57 个 >50 行函数（20+ 在生产代码中） | 多个文件 | 可维护性 |
| P2-2 | 代码质量 | `routes/v3_adapters.py` 4 次重复 lazy import 同一函数 | `routes/v3_adapters.py` | 代码异味 |
| P2-3 | 代码质量 | 多个 routes 直接 import 底层模块（跨层耦合） | `routes/` 多个文件 | 架构边界模糊 |
| P2-4 | 代码质量 | pyright `search_gateway/` 幻影路径 | `pyrightconfig.json` | 类型检查配置无效 |
| P2-5 | 代码质量 | ruff `backends.py` 幻影豁免 + 6 个不存在路径 | `ruff.toml` | 配置噪音 |
| P2-6 | 代码质量 | 20 个文件在 250-300 行区间，多个测试文件 ≥250 行 | 多个文件 | 临近违规风险 | ✅ 已完成（>300 行文件已清零；250-300 行文件已处理）|
| P2-7 | 测试 | `context_pipeline/` 17 模块零覆盖 | `context_pipeline/` | 流水线核心无测试 |
| P2-8 | 测试 | `session_memory/` 22 模块零覆盖（含 `redact.py` 脱敏） | `session_memory/` | 持久化/安全无测试 |
| P2-9 | 测试 | `routes/` ~55 模块零覆盖 | `routes/` | HTTP 路由层无测试 |
| P2-10 | 测试 | `time.time()` 用于测试数据（10+ 文件） | ~10 个测试文件 | 时间相关逻辑 flaky |
| P2-11 | 测试 | `test_routing_engine_integration.py` 误导性命名 | 测试文件 | 假装集成测试 |
| P2-12 | 架构 | REST/WS/MQTT 三通道消息处理逻辑不统一 | `routes/device_gateway*.py` | 行为不一致 |
| P2-13 | 架构 | `_run_coro_sync` sync/async 桥接模式重复实现 | 2 个文件 | 重复代码+调试困难 |
| P2-14 | 架构 | 3 套 device store 模式重复但不共享抽象 | 3 个 store 模块 | 重复代码 |
| P2-15 | 架构 | `context_pipeline/` 4+ 模块仅被测试引用 | 4 个模块 | 维护负担 |
| P2-16 | 安全 | 生产后端使用 HTTP 明文传输（虽默认禁用） | `backends_registry/community_free.py` | API key 明文 |
| P2-17 | 安全 | VPS 内部代理使用 HTTP 跨公网 | `backends_registry/coding_pool/third_party.py` | 明文通信 |
| P2-18 | 安全 | 缺少 CSP header | `routes/security_headers.py` | Admin 面板防护不足 |
| P2-19 | 安全 | 多处 `logger.debug` 静默降级违反硬规则 | 7+ 个文件 | 隐蔽故障 |
| P2-20 | 安全 | `session_memory/processor.py:50` 记忆处理静默返回空列表 | `session_memory/processor.py` | 数据丢失风险 |
| P2-21 | 代码质量 | 重复的复杂度评估逻辑（3 套独立实现） | 3 个模块 | 决策不一致 |

### P3 — 低优先级改善（20 项）

| ID | 维度 | 缺陷 | 文件 | 影响 |
|----|------|------|------|------|
| P3-1 | 代码质量 | `health_tracker.py` 导出私有全局变量 | `health_tracker.py:36-48` | 封装泄露 |
| P3-2 | 代码质量 | 健康子系统 6 模块碎片化，内部 lazy import 循环依赖 | `health_*.py` | 维护负担 |
| P3-3 | 代码质量 | `context_pipeline/__init__.py` RequestContext 定义但未使用 | `context_pipeline/__init__.py` | 架构意图脱节 |
| P3-4 | 代码质量 | `context_pipeline/response_pipeline.py` ResponsePipeline 定义但未使用 | `context_pipeline/response_pipeline.py` | 架构意图脱节 |
| P3-5 | 测试 | 2 个永远 skip 的死测试 | `test_p1_4_device_stability_gate*.py` | 代码噪声 |
| P3-6 | 测试 | `test_pipeline_integration.py` 无断言测试 | 测试文件 | 空洞测试 |
| P3-7 | 测试 | `xiaozhi_schema/test_triggers.py` 8× `sleep(1.1)` | 测试文件 | 慢测试（~9s） |
| P3-8 | 测试 | `assert True` 占位断言 | `device_gateway_profile/` | 低价值测试 |
| P3-9 | 测试 | 多个测试低断言密度（<0.5 断言/测试） | `device_voice/` 测试 | 质量低 |
| P3-10 | 架构 | `pick_backend()` 承担 7 个顺序步骤 | `routing_engine.py:108-156` | 单一职责违反 |
| P3-11 | 架构 | `routing_engine.route()` 隐式承担 12+ 职责（上帝函数） | `routing_engine.py` | 可维护性 |
| P3-12 | 架构 | 重复的 complexity 评估（route 调用链中两次评估） | `routing_engine_execute_strategy.py:30` | 冗余计算 |
| P3-13 | 架构 | `speculative_execution.py` sync→async 桥接导致线程嵌套 | `speculative_execution.py:57-77` | 调试困难 |
| P3-14 | 架构 | SQLite 无连接池，每次操作新建连接 | 15+ 个模块 | 并发性能差 |
| P3-15 | 架构 | device_gateway 目录膨胀（54 文件，含过度拆分的 task 模块） | `device_gateway/` | 导航困难 |
| P3-16 | 安全 | Client Keys 仅内存存储，重启后丢失 | `routes/admin_extra_client_keys.py:15` | 运维缺陷 |
| P3-17 | 安全 | `paramiko>=3.4.0` 可能有已知 CVE | `requirements_server.txt` | 建议升级 >=3.5.0 |
| P3-18 | 安全 | JDCloud 部署脚本硬编码 IP + 重复脚本 | `deploy/jdcloud/` | 运维不便 |
| P3-19 | 代码质量 | `device_gateway/task_deps.py` 仅 18 行，可合并 | `device_gateway/task_deps.py` | 过度拆分 |
| P3-20 | 代码质量 | ruff exclude 未排除 `.venv310/`、`.test-tmp/`、`.pnpm-store/` | `ruff.toml` | 可能误扫描 |

---

## 3. P0 — 必须立即修复

### P0-1：`backend_reputation.py` 全局可变状态无线程保护 ✅ 已修复

**文件**：`backend_reputation.py:10-14`

**问题**：
```python
_scores: dict[str, float] = {}
_history: dict[str, list] = {}
_cooldowns: dict[str, float] = {}
```

这三个全局字典被 `record()`、`record_failure_class()`、`get_score()`、`is_reputation_cooled()`、`sort_by_reputation()` 等函数读写，但**没有任何锁保护**。在 FastAPI 的多线程环境中（`asyncio.to_thread` 调用同步路由函数），这是一个**数据竞争 bug**。

**影响**：并发请求可能导致信誉分数计算错误，进而影响后端选择决策。

**修复方案**：
```python
import threading
_lock = threading.RLock()
_scores: dict[str, float] = {}
_history: dict[str, list] = {}
_cooldowns: dict[str, float] = {}

# 所有读写操作用 with _lock: 保护
def record(backend: str, success: bool, ...):
    with _lock:
        _scores[backend] = ...
        _history[backend].append(...)
```

**验证**：
- 新增 `tests/test_backend_reputation_threading.py`：并发 100 线程同时调用 `record()` 和 `get_score()`
- 确保最终状态一致、无异常
- `ruff check` / `pyright` clean

**预估工作量**：0.5 人天

---

### P0-2：MQTT 同步回调中使用 `asyncio.get_event_loop()` ✅ 已修复

**文件**：`device_gateway/mqtt_client.py:104`

**问题**：
```python
# 在 MQTT on_message 回调中（同步线程）
asyncio.get_event_loop().create_task(...)
```

`asyncio.get_event_loop()` 在 Python 3.10+ 中已弃用，且在同步线程中调用时：
- 如果当前线程没有运行的事件循环 → `RuntimeError`
- 如果有事件循环但不是目标循环 → task 被创建到错误的循环中

**影响**：MQTT 消息转发在特定条件下崩溃，设备 motion_event 丢失。

**修复方案**：
```python
# 启动时保存主事件循环引用
_main_loop: asyncio.AbstractEventLoop | None = None

def set_main_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop

# 在 on_message 回调中
if _main_loop and _main_loop.is_running():
    asyncio.run_coroutine_threadsafe(_handle_motion_event(data), _main_loop)
else:
    _log.warning("MQTT message received but no running event loop; dropping event")
```

**验证**：
- 新增测试：模拟无事件循环时的回调行为
- 确保 warning 日志输出
- `ruff check` / `pyright` clean

**预估工作量**：0.5 人天

---

### P0-3：Admin 配置导入端点缺少 URL 安全验证 ✅ 已修复

**文件**：`routes/admin_extra_config.py:36-46`

**问题**：
```python
@router.post("/api/config/import", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def config_import(req: Request):
    body = await req.json()
    new_backends = body.get("backends", {})
    for name, cfg in new_backends.items():
        if name not in BACKENDS:
            BACKENDS[name] = cfg  # 直接注入，无 _is_safe_backend_url 验证！
```

对比 `admin_api.py:124` 中的 `admin_add_backend` 正确调用了 `_is_safe_backend_url()`。此端点绕过了 URL 安全验证。

**影响**：获取 admin token 的攻击者可注入内网 URL 或 HTTP 后端，导致 SSRF。

**修复方案**：
```python
from routes.admin_api import _is_safe_backend_url

@router.post("/api/config/import", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def config_import(req: Request):
    body = await req.json()
    new_backends = body.get("backends", {})
    for name, cfg in new_backends.items():
        if name not in BACKENDS:
            url = cfg.get("base_url", "")
            if not _is_safe_backend_url(url):
                return JSONResponse({"error": f"unsafe URL for backend {name}"}, status_code=400)
            BACKENDS[name] = cfg
```

**验证**：
- 新增测试：注入 `http://127.0.0.1:8080` URL 应被拒绝
- 新增测试：正常 HTTPS URL 应被接受
- `ruff check` clean

**预估工作量**：0.25 人天

---

### P0-4：`.gitignore` 缺失关键目录 ✅ 已修复

**文件**：`.gitignore`

**问题**：以下实际存在的目录未在 `.gitignore` 中排除：

| 目录 | 存在 | 在 .gitignore | 风险 |
|------|------|--------------|------|
| `.test-tmp/` | ✅ | ❌ | 测试临时文件误提交 |
| `.pnpm-store/` | ✅ | ❌ | pnpm 缓存误提交 |
| `.venv310/` | ✅ | ❌（仅排除 `venv/` 和 `.venv`） | 虚拟环境误提交 |

**修复方案**：在 `.gitignore` 中追加：
```
.test-tmp/
.pnpm-store/
.venv310/
```

**验证**：`git status` 不再显示这些目录的内容。

**预估工作量**：0.1 人天

---

### P0-5：意外空文件 `=6.0` 残留在根目录 ✅ 已修复

**文件**：`=6.0`（根目录）

**问题**：0 字节空文件，极可能是 shell 重定向意外产物（如 `pip install something >=6.0` 被解析为创建文件 `=6.0`）。

**修复方案**：删除该文件。

**预估工作量**：0.05 人天

---

### P0-6：`test_external_enrichment.py` 隐藏网络依赖 ✅ 已修复

**文件**：`tests/test_external_enrichment.py:56-80`

**问题**：
```python
def test_weather_provider_uses_cache():
    provider = OpenMeteoProvider(cache, limiter)
    result1 = provider.get_weather(40.7, -74.0)  # 真实网络调用！
    assert result1 is not None  # 如果无网络或 API 宕机 → 失败
```

两个测试直接调用外部 API（Open-Meteo、Nager.Date），无 mock、无 `importorskip`、无 marker 标记。在无网络环境下会失败。

**修复方案**：
1. 使用 `pytest.mark.network` marker 标记
2. 或使用 `unittest.mock.patch` mock HTTP 调用
3. 在 `pytest.ini` 注册 marker，默认跳过 network 测试

**验证**：
- 无网络时 `pytest tests/test_external_enrichment.py -q` 应 skip 而非 fail
- 有网络时显式 `--run-network` 可运行

**预估工作量**：0.5 人天

---

## 4. P1 — 高优先级修复

### P1-1：SQLite `check_same_thread=False` 无锁保护 ✅ 已修复

**文件**：`code_context/sqlite_graph_store.py:29`、`device_logic/db.py:62`

**问题**：使用 `sqlite3.connect(path, check_same_thread=False)` 但没有加锁保护。多线程并发写入时可能损坏数据库。

**修复方案**：
- `code_context/sqlite_graph_store.py` 已在 `__init__` 中创建 `self._lock = threading.RLock()`，所有 `add_relation`、`get_related`、`edge_count` 等读写操作均受 `with self._lock:` 保护。
- `device_logic/db.py` 已迁移至 `config/sqlite_pool.pooled_sqlite_conn`，由连接池代理管理线程安全。

**验证**：新增 `tests/test_sqlite_graph_store_threading.py`，10 线程 × 50 次并发写入及混合读写通过，数据库完整性一致。

**预估工作量**：1 人天

---

### P1-2：环境变量读取极度分散，无集中配置

**文件**：148 个文件中 496 处 `os.getenv`/`os.environ` 调用

**问题**：
- `backends_registry/cloudflare.py` 同一文件内读取 `CLOUDFLARE_ACCOUNT_ID` 各 16 次
- 模块加载时 vs 运行时读取不一致
- 没有统一的配置校验和默认值管理

**修复方案**：
1. 新建 `config.py` 集中配置模块（或扩展现有 `brand_config.py`）
2. 按域分组：`DatabaseConfig`、`RedisConfig`、`BackendConfig`、`SecurityConfig` 等
3. 使用 `pydantic-settings` 或 dataclass 管理配置
4. 所有模块从 `config.py` 导入配置对象，不再直接调用 `os.environ`
5. 模块加载时统一读取，运行时不可变

**分阶段实施**：
- 阶段 1：集中数据库/Redis 相关配置（约 50 处）✅ 已完成（`config/db_config.py`）
- 阶段 2：集中后端/Cloudflare 相关配置（`backends_registry/` 全部凭证与隧道 URL）✅ 已完成
  - `config/backend_config.py` 已新增 Cloudflare 凭证、高频后端 API Key、中文商业 Key、社区免费 Key、平台 Key、隧道 URL、VPS_HOST、编码池 Key 等。
  - 本轮完成所有 `backends_registry/` 模块的环境变量读取迁移（`__init__.py` 的 overlay 加载除外，已无 `os.environ.get` 直接读取后端凭证）。
  - 已迁移文件：
    - 高频：`backends_registry/groq.py`、`mistral.py`、`openrouter.py`、`github.py`、`google.py`、`nvidia.py`、`modelscope.py`、`coding_pool/modelscope.py`。
    - 中文商业：`backends_registry/commercial/chinese.py`。
    - 社区免费：`backends_registry/community_free.py`、`backends_registry/coding_pool/community.py`。
    - 平台/其他商业：`backends_registry/commercial/cerebras_family.py`、`backends_registry/commercial/opengateway.py`、`backends_registry/commercial/platforms.py`。
    - VPS 代理/隧道：`backends_registry/vps_proxies.py`、`backends_registry/free_web_ddg.py`、`backends_registry/misc.py`。
    - 编码池：`backends_registry/coding_pool/third_party.py`。
- 阶段 3：集中其余配置（运行时、数据库、Redis、安全等）→ 进行中
  - `config/settings.py` 新增 `EvalConfig`（`LIMA_EVAL_TOPOLOGY`、`LIMA_EVAL_VIA_ROUTER_URL`、`LIMA_EVAL_WINDOWS_ROUTER`）、`FeatureFlags.device_llm_planner`、`MonitoringConfig.sentry_dsn`、`DeviceConfig`、`SessionMemoryConfig`（含 `LIMA_SESSION_MEMORY`、`LIMA_MEMORY_ADMIN`、`LIMA_MEMORY_INBOX`、`LIMA_MEMORY_CONSOLIDATION_INTERVAL`、`LIMA_OUTCOME_LEDGER`、`LIMA_OUTCOME_DB`、`JINA_API_KEY`）、`FeatureFlags.allow_http_backends`、`BackendOpsConfig`（`LIMA_PROBE_INTERVAL`、`LIMA_OPERATOR_PROBE_TIMEOUT`、`LIMA_OPERATOR_PROBE_WORKERS`、`LIMA_BACKEND_RETIREMENT_RELOAD_SEC`、`LIMA_DYNAMIC_ADMISSION`）。
  - 迁移 `eval_topology.py` 的 `LIMA_API_KEY` / eval URL / 开关到 `config.settings`。
  - 迁移 `vision_handler.py`、`http_stream.py`、`http_caller.py` 的 `LIMA_DEBUG` 到 `config.settings.FLAGS.debug`。
  - 迁移 `device_gateway/intent.py` 的 `LIMA_DEVICE_LLM_PLANNER` 到 `config.settings.FLAGS.device_llm_planner`。
  - 迁移 `server.py` 的 `SENTRY_DSN` 到 `config.settings.MONITORING.sentry_dsn`。
  - 迁移 `device_gateway/auth.py` / `mqtt_client.py` / `notifier.py` / `redis_store.py` / `redis_store_helpers.py` 的设备相关环境变量到 `config.settings.DEVICE`。
  - 迁移 `session_memory/daemon.py` / `embeddings.py` / `outcome_ledger/config.py` / `outcome_ledger/record.py` / `processor.py` / `store_admin.py` / `store_db.py` 的会话记忆相关环境变量到 `config.settings.SESSION_MEMORY`。
  - 迁移 `http_sync.py` 的 `LIMA_ALLOW_HTTP_BACKENDS` 到 `config.settings.FLAGS.allow_http_backends`。
  - 迁移 `backend_probe_loop.py` / `backend_retirement.py` / `backend_admission_store.py` 的后端运维环境变量到 `config.settings.BACKEND_OPS`。
  - 迁移 `brand_config.py` / `backends_constants.py` 的品牌相关环境变量到 `config.settings.BRAND`。
  - 迁移 `code_context/embedding_client.py` / `session_memory/embeddings.py` 的 Jina 嵌入配置到 `config.settings.EMBEDDING`。
  - 迁移 `context_pipeline/auto_indexer.py` 的 `LIMA_PROJECT_ROOT` 到 `config.settings.PATHS.project_root`。
  - 迁移 `dashscope_image_client.py` 的 `ALIYUN_API_KEY` 到 `config.backend_config.ALIYUN_API_KEY`。
  - 清理 `channel_retirement.py`：删除已退役 Telegram 的 `_telegram_bot_token()` / `retire_telegram_webhook_from_env()` 及对应 env 读取，仅保留 `mark_retired_modules` / `is_retired_route_path`。
  - 重构 `config/env.py`：所有函数改从 `config.settings`（及 `config.backend_config.GOOGLE_AI_KEY`）读取，不再直接调用 `os.environ`；新增 `DigitalHumanConfig`、`VoiceConfig`、`GeminiConfig`、`OutcomeConfig`、`OtaConfig`、`UploadConfig` 到 `config.settings`，并扩展 `FeatureFlags`。
  - `device_voice` 配置集中化：新增 `config/voice_settings.py`，将 `VoiceConfig`、`VoiceprintConfig`、`VoiceProviderConfig` 及各 ASR/TTS Provider 配置类移出 `config/settings.py`；`device_voice/__init__.py`、`voiceprint.py`、`providers/vad_silero.py` 与全部 ASR/TTS provider 模块改从 `config.settings` 读取，不再直接调用 `os.environ`。
  - `tests/conftest.py` monkeypatch wrapper 增强并拆分：`_EnvSyncMonkeyPatch` 拆出到 `tests/_env_sync.py`，映射数据进一步拆到 `tests/_env_sync_maps.py` 与 `tests/_env_sync_voice_maps.py`，避免单文件/单函数过大；新增 voice / voiceprint / voice provider 环境变量同步。
  - `config/db_config.py` 新增 `get_session_db_path()` 与 `REQUEST_LOG_DB`，`device_gateway/family_approval_store.py`、`session_memory/store_db.py`、`routing_loop/request_store.py` 改从 `config.db_config` 读取数据库路径。
  - 集中核心运行时模块：
    - `rate_limiter_redis.py`：`LIMA_DEVICE_AUTH_RATE_REDIS` / `LIMA_DEVICE_AUTH_RATE_REDIS_URL` → `settings.SECURITY`
    - `token_health.py`：`$ENV_VAR` 形式的后端 key 解析 → `settings.resolve_backend_key()`
    - `key_pool.py`：`LIMA_KEY_POOL_*` → `settings.get_key_pool_raw()`
    - `routing_loop/request_store.py`：`LIMA_REQUEST_LOG_DB` → `settings.DB.request_log_db`
    - `device_logic/auth.py` / `auth_rate.py` / `activation.py` / `sms.py`：`LIMA_JWT_SECRET`、`LIMA_DEVICE_AUTH_*_PER_MIN`、`LIMA_XIAOZHI_ACTIVATION_CODE`、`LIMA_XIAOZHI_LOGIN_CODE`、`LIMA_XIAOZHI_CAPTCHA_REQUIRED` → `settings.SECURITY` / `settings.DEVICE`
    - `http_request_builder/client.py`：`GFW_PROXY` → `settings.EMBEDDING.gfw_proxy`
    - `http_request_builder/headers.py`：动态 `key_env_var` / `{BACKEND}_API_KEY` env 读取 → `settings.get_env()`
    - `integrations/cloud_services.py`：`SUPABASE_URL` / `SUPABASE_SECRET` / `LANGSMITH_API_KEY` → `settings.INTEGRATIONS`
    - `local_retrieval/leann_adapter.py`：`LIMA_ENABLE_LEANN` → `settings.FLAGS.enable_leann`
    - `runtime_env.py` / `runtime_topology.py` / `healthcheck_ping.py` / `context_pipeline/_project_root.py` / `device_mode.py` / `orchestrate_constants.py`：运行时开关/拓扑/健康检查/项目根目录/设备模式相关 env → `settings.FLAGS` / `settings.PATHS`
    - `config/settings.py` 拆分为 facade（`config/settings.py`）与核心 dataclass（`config/settings_core.py`），避免单文件超过 300 行；新增 `FleetConfig`、`EmbeddingConfig.google_inventory_proxy` / `mcp_inventory_proxy`、`DatabaseConfig.tool_audit_db` / `worker_db`、`PathsConfig.code_dir` / `routing_model_path`、`DeviceConfig.redis_memory_index_ttl` / `redis_ledger_ttl`、`IntegrationsConfig.gitee_token`
    - `config/eval_config.py`：新增 eval 专用配置模块，集中 `LIMA_EVAL_BASE_URL`、`LIMA_EVAL_QUICK_BACKENDS`、`LIMA_EVAL_FULL_BACKENDS`、`LIMA_PERIODIC_CODING_EVAL`、`LIMA_CODING_EVAL_INTERVAL_HOURS`、`LIMA_PERIODIC_EVAL_NOTIFY`、`LIMA_PERIODIC_CODING_EVAL_FULL`、`LIMA_EVAL_POOL_GATE`、`LIMA_EVAL_POOL_MIN_SCORE`
    - `eval_preflight.py` / `eval_notify.py` / `periodic_coding_eval.py` / `eval_pool_gate.py`：改从 `config.eval_config` 读取
    - `device_memory/redis_store.py` / `device_ledger/redis_store.py`：`LIMA_REDIS_MEMORY_INDEX_TTL` / `LIMA_REDIS_LEDGER_TTL` → `settings.DEVICE`
    - `tool_gateway/audit.py` / `tool_gateway/governance.py`：`LIMA_AUDIT_DB` / `LIMA_WORKER_DB` → `settings.DB`
    - `context_pipeline/code_scanner.py`：`LIMA_CODE_DIR` → `settings.PATHS.code_dir`
    - `think_plan_context.py`：`LIMA_PROJECT_ROOT` → `settings.PATHS.project_root`
    - `routing_ml/routing_trainer.py`：`LIMA_ROUTING_MODEL_PATH` → `settings.PATHS.routing_model_path`
    - `fleet/agent.py`：`LIMA_FLEET_ALLOWED_COMMANDS` → `settings.FLEET`
    - `routing_selector/helpers.py`：动态 `$ENV_VAR` key 存在性检查 → `settings.get_env()`
    - `backends_registry/_utils.py`：`legacy_free_enabled` 改通过 `settings.get_env()` 检测变量存在
    - `gitee_mirror_urls.py`：`GITEE_TOKEN` / `GITEE_ACCESS_TOKEN` → `settings.INTEGRATIONS.gitee_token`
    - `provider_automation/adapters/gitee_ai.py`：`GITEE_AI_ENABLED` / `GITEE_AI_TOKEN` / `GITEE_AI_BASE_URL` → `config.backend_config`
    - `provider_inventory/google.py`：`GOOGLE_AI_KEY` / `GOOGLE_INVENTORY_PROXY` → `config.backend_config` / `settings.EMBEDDING`
    - `provider_inventory/mcp_registries.py`：`MCP_INVENTORY_PROXY` / `GFW_PROXY` → `settings.EMBEDDING`
    - `device_gateway/store_utils.py`：`configure_from_env` 改通过 `settings.get_env()` 读取后端选择变量
    - `device_voice/providers/_env.py`：动态别名 env 读取 → `settings.get_env()`
    - `tests/_env_sync_maps.py` 进一步拆出 `tests/_env_sync_runtime_maps.py`，并为上述新增字段补充映射；wrapper 特判 `GITEE_AI_*` 同步到 `config.backend_config`
  - `tests/conftest.py` 新增 `monkeypatch` wrapper，在测试通过 `monkeypatch.setenv/delenv` 修改环境变量时同步更新 `config.settings` 单例，保证既有测试无需大量改写。
  - 更新 `tests/test_device_gateway_auth.py`、`tests/test_memory_admin.py`、`tests/test_session_memory.py`、`tests/test_session_memory_processor.py`、`tests/test_http_scheme_enforcement.py`、`tests/test_routes_chat_stream.py` 以 patch 单例或利用 wrapper。

**验证**：
- 迁移后的后端定义模块聚焦测试：`tests/test_backends*.py`、`tests/test_routes_admin_api.py`、`tests/test_routes_admin_backends.py`、`tests/test_admin_backends.py` → 51 passed
- device/session/http 聚焦测试：`tests/test_device_gateway*.py`、`tests/test_session_memory*.py`、`tests/test_http*.py`、`tests/test_family_approval*.py`、`tests/test_memory_admin.py` → 243 passed
- 后端运维聚焦测试：`tests/test_backend_probe_loop.py`、`tests/test_backend_retirement.py`、`tests/test_backend_admission*.py` → 18 passed
- 品牌/嵌入聚焦测试：`tests/test_brand_config.py`、`tests/test_code_context*.py`、`tests/test_session_memory*.py` → 83 passed
- 退役/索引/图生聚焦测试：`tests/test_channel_retirement.py`、`tests/test_context_pipeline*.py`、`tests/test_dashscope*.py` → 53 passed
- config.env / admin / digital-human / gemini / system 聚焦测试：`tests/test_admin_auth.py`、`tests/test_routes_admin_auth.py`、`tests/test_routes_digital_human.py`、`tests/test_routes_gemini_live_proxy.py`、`tests/test_routes_system_endpoints.py`、`tests/test_routes_device_gateway_ws_handlers.py` → 51 passed
- device_voice 聚焦测试：`tests/device_voice/` + `tests/test_routes_voice_pipeline_ws.py` + `tests/test_routes_digital_human.py` → 85 passed
- eval/tool/routing/fleet/gitee 聚焦测试：`tests/test_eval_*.py`、`tests/test_periodic_coding_eval.py`、`tests/test_tool_gateway_audit.py`、`tests/test_tool_gateway_governance.py`、`tests/test_routing_selector_helpers.py`、`tests/test_routing_ml.py`、`tests/test_fleet_agent.py`、`tests/test_gitee_mirror.py`、`tests/test_gitee_ai_adapter.py`、`tests/test_provider_inventory.py` → 196 passed
- 代码尺寸：拆分 env sync wrapper、voice settings、runtime maps 与核心长函数后，已无 >300 行文件；`scripts/check_code_size.py` 剩余 25 个 >50 行函数（均为脚本/测试/MCP，核心生产代码已清零）
- 全量 `.venv310/Scripts/python.exe -m pytest --tb=short -q`：**3545 passed, 17 skipped, 2 deselected**
- `ruff check` / `pyright` 修改文件 clean

**预估工作量**：3 人天（分阶段）

---

### P1-3：`routing_engine_context.py` 延迟导入+异常吞没 ✅ 已修复

**文件**：`routing_engine_context.py:10-93`

**问题**：`try_recall_backend()`、`inject_coding_context()`、`assess_complexity()`、`auto_compress()` 全部使用 `try/except ImportError` + `except Exception` 模式。如果 `context_pipeline` 子模块有 bug，整个路由流水线会**静默降级**。

**修复方案**：
- `ImportError` 保留（可选依赖），日志已从 `debug` 提升到 `warning`，并附带异常原因。
- `except Exception` 的日志已从 `debug` 提升到 `warning`，并附带 `exc_info=True` 输出 traceback。

**验证**：新增 `tests/test_routing_engine_context_warnings.py`，模拟 `code_context_injection`、`session_memory.store_promote`、`context_pipeline.complexity` 抛出异常，验证均输出 warning 日志且不阻断主流程。

**预估工作量**：1 人天

---

### P1-4：88 处 `except Exception` 仅 debug log（LiMa 核心已修复） ✅

**文件**：多个文件（详见架构分析报告）

**问题**：违反 AGENTS.md 硬规则 #1（禁止静默降级）。`_log.debug` 级别在生产环境中几乎不可见。

**修复结果**：
- LiMa 核心代码中 `except Exception` 后仅 `_log.debug` 的位置已清零；生产路径均提升为 `_log.warning(..., exc_info=True)` 或显式重抛。
- 当前仅 `reference/ECC/`（顾问参考仓库）与 `esp32S_XYZ/`（vendored 固件代码）残留 7 处，非 LiMa 生产路径。
- 剩余 2 处疑似静默降级（`coding_backend_scorer.py:43`、`device_gateway/profiles.py:259`）已纳入 P2-19 跟踪并修复。

**验证**：全量 `ruff check .` / `pytest` 通过；核心路径扫描无 debug-only 异常处理。

**预估工作量**：2 人天（已完成核心修复）

---

### P1-5：routing_executor 系列零测试覆盖 ✅ 已修复

**文件**：`routing_executor.py`、`routing_executor_fallback.py`、`routing_executor_parallel.py`、`routing_executor_serial.py`、`routing_executor_telemetry.py`

**问题**：核心路由执行路径（串行/并行/降级/遥测）完全无测试覆盖。

**修复方案**：
1. `tests/test_routing_executor_serial.py`：串行执行、成功/失败/超时/空列表/tools
2. `tests/test_routing_executor_parallel.py`：并行执行、部分失败、全部失败、短回答、空列表
3. `tests/test_routing_executor_fallback.py`：降级候选选择、串行降级、并行降级、全部失败
4. `tests/test_routing_executor.py`（新增）：`execute()`  orchestration 端到端，包括成功、fallback、exhausted、tools 时 `max_tries` 边界
5. `tests/test_routing_executor_telemetry.py`（新增）：`extract_error_code` 各种异常、`_record_backend_attempt` telemetry 缺失/失败降级

**验证**：5 个测试文件全部通过，覆盖正常与异常路径。

**预估工作量**：3 人天

---

### P1-6：`device_gateway/auth.py`、`safety.py` 零测试覆盖 ✅ 已修复

**文件**：`device_gateway/auth.py`、`device_gateway/safety.py`

**问题**：认证和安全核心模块无测试。

**修复方案**：
1. `tests/test_device_gateway_auth.py`：token 解析（逗号/分号/换行分隔）、有效/无效 token、未知设备、空 token、默认数字人 fallback、`token_configured`
2. `tests/test_device_gateway_safety.py`：`safe_point` 边界与异常、`validate_run_path_params` 各种有效/无效输入、常量断言

**验证**：两个测试文件均已存在且全部通过，用例数 ≥15。

**预估工作量**：2 人天

---

### P1-7：模块级 `os.environ` 赋值不清理 ✅ 已修复

**文件**：多个测试文件（详见测试分析报告）

**问题**：模块顶层直接修改 `os.environ`，整个 test session 期间生效，影响并行测试。

**修复方案**：
- 将 `tests/test_routes_chat_endpoints.py`、`tests/test_typed_memory.py`、`tests/test_xiaozhi_compat_route_policy.py` 等顶部 `os.environ.setdefault()` 改为 `monkeypatch.setenv()` fixture。
- 使用 `tmp_path` 替代 `tempfile.gettempdir()` 避免文件争抢。
- 删除 `tempfile.mktemp()` 使用（已废弃）。

**验证**：聚焦测试通过；全量测试无回归。

**预估工作量**：1 人天

---

### P1-8：10 份完全相同的 `design_system.py` 副本 ✅ 已修复

**文件**：9 个 agent 配置目录中的 `skills/ui-ux-pro-max/scripts/design_system.py`（实际定位到 9 份；`.claude/` 作为主副本）

**问题**：1067 行 × 9 副本 ≈ 387KB 纯重复；所有副本哈希一致。

**修复方案**：
- 保留主副本：`.claude/skills/ui-ux-pro-max/scripts/design_system.py`。
- 其余 8 个目录中的 `design_system.py` 替换为自动生成的 exec stub（24 行），运行时动态加载主副本，保留 `python design_system.py` 与 `import design_system` 两种使用方式。
- 新增 `scripts/sync_design_system_stubs.py`，用于重新生成/同步 stub。
- 这些 agent 配置目录原本已在 `.gitignore` 中排除；本次变更减少工作区重复内容。

**验证**：
- `python .agent/skills/ui-ux-pro-max/scripts/design_system.py --help` 正常输出。
- `import design_system` 从 stub 目录导入成功，`generate_design_system` 可用。
- 全量测试无回归。

**预估工作量**：0.5 人天

---

### P1-9：`context_pipeline/` 死代码清理 ✅ 已修复

**文件**：`graph_context_expander.py`、`retrieval_trace.py`、`production_index.py`、`entity_extraction.py`

**问题**：这些模块仅被测试引用或 lazy import（带 fallback），生产路径中实际不执行。

**修复方案**：
1. 运行 `python scripts/codegraph_orphans.py --fanin` 确认零引用
2. 删除模块和对应测试
3. 更新 `CODEBASE_COLD_PRUNE_PRIORITY_CN.md`
4. 更新 `pyrightconfig.json` 和 `ruff.toml`

**实际结果**：四个模块已在 `refactor(slimming): round 6` 提交（`2f8fdea5`）中删除；当前工作区确认文件不存在，无生产引用残留。无需进一步清理。

**预估工作量**：0.5 人天

---

### P1-10：重复的复杂度评估逻辑 ✅ 已修复

**文件**：`context_pipeline/complexity.py` vs `speculative_policy.py:110`

**问题**：两套独立的请求复杂度评估系统，功能重叠但实现不同，可能导致重复计算和决策不一致。

**修复方案**：
1. 以 `speculative_policy.classify_complexity` 为权威实现（更简单、已在执行路径中）
2. `context_pipeline/complexity.py` 改为 re-export 或删除
3. `routing_engine_context.py` 中的 `assess_complexity` 调用改为使用统一接口
4. 确保 `assess_code_complexity`（语义代码检索）保留独立职责

**实际结果**：
- 将统一评分逻辑迁移到 `speculative_policy.score_request`，`classify_complexity` 直接复用该分数。
- `context_pipeline/complexity.py` 改为兼容性 re-export，保留 `ComplexityAssessment`、`assess_complexity`、`dynamic_ensemble_decision` 供历史调用点使用。
- `routing_engine_context.assess_complexity` 继续通过 `context_pipeline.complexity` 调用统一接口。
- 全量测试 `3513 passed, 17 skipped`；`ruff` / `pyright` clean。

**预估工作量**：1 人天

---

### P1-11：部署脚本通过 HTTP 下载 Prometheus ✅ 已修复

**文件**：`deploy/jdcloud/deploy_jd.py:19`

**问题**：`wget http://47.112.162.80:8888/prometheus.tar.gz` — HTTP 下载无完整性校验。

**修复方案**：
- 已改为从 GitHub Releases HTTPS 下载 `prometheus-2.45.0.linux-amd64.tar.gz`。
- 已新增 SHA256 校验：`1c7f489a3cc919c1ed0df2ae673a280309dc4a3eaa6ee3411e7d1f4bdec4d4c5`。

**验证**：
- 脚本执行时 `sha256sum -c` 校验；失败即退出。
- 新增回归测试 `tests/test_deploy_jd_prometheus.py`：断言下载 URL 使用 HTTPS 且存在 64 位十六进制 SHA256 校验值。

**预估工作量**：0.5 人天

---

### P1-12：`device_logic/auth.py` 认证异常静默返回 False ✅ 已修复

**文件**：`device_logic/auth.py:50-51`

**问题**：
```python
except Exception:
    return False  # 认证异常被静默吞没
```

认证系统故障时返回 `False`（认证失败），与"凭证错误"无法区分，可能掩盖安全漏洞。

**修复方案**：
- `_verify_password()` 中对 `Exception` 已记录 `_log.error(..., exc_info=True)` 后再返回 `False`。
- `ValueError`（hash 格式损坏）原被静默吞没，现改为记录 `_log.warning(...)` 后再返回 `False`，以便区分用户凭证错误与系统存储异常。
- 其他认证路径的异常不再静默吞没。

**验证**：新增 `tests/test_device_logic_auth.py` 覆盖正常/错误密码、空 hash、hash 损坏、bcrypt 异常及 `make_token` JWT 缺失分支；全量测试通过。

**预估工作量**：0.25 人天

---

## 5. P2 — 中优先级修复

### P2-1：57 个 >50 行函数 ✅ 已修复

**范围**：生产代码中 20+ 个函数超过 50 行

**修复方案**：按热度排序，优先拆分路由执行路径、设备网关和语音 ASR 中的长函数。经过多轮拆分，>50 行函数从 57 降至 **25**（满足验收标准 <40，核心生产代码已清零，剩余均为脚本/MCP/测试）。

**本轮拆分**：
- `session_memory/learning_loop/memory_channel.py`：`_feed_memory` 拆为 `_save_test_result_memories` / `_save_outcome_memory` / `_save_changed_file_memories`
- `routes/admin_backends.py`：`test_backend_sync` 拆为 `_build_probe_request` / `_send_probe_request`
- `routes/device_voice_ws_helpers.py`：`_extract_and_store_voiceprint_embedding` 拆为 `_extract_voiceprint_embedding` / `_persist_voiceprint_embedding`
- `routes/chat_preflight.py`：`prepare_chat_preflight` 拆为 `_build_prompt_context_from_request`
- `routes/digital_human.py`：`_serialize_config_script` 拆为 `_script_boilerplate` / `_append_force_set_inputs` / `_append_voice_config` / `_append_advanced_config` / `_script_footer`
- `session_memory/outcome_ledger/record.py`：`record_evidence` 拆为 `_record_evidence_core` / `_build_evidence_result`
- `device_policy/engine.py`：`decide` 拆为 `_protocol_gate` / `_profile_safety_gate`
- `device_voice/providers/asr_aliyun.py`：`_run_streaming_worker` 拆为 `_create_streaming_transcriber` / `_start_streaming_transcriber` / `_feed_audio_until_end` / `_stop_and_wait`，并将流媒体相关 helper/state/error 映射移入 `device_voice/providers/_asr_aliyun_worker.py`
- `routes/chat_stream.py`：`stream_response` 引入 `_stream_text_response` 分发器；`_stream_sentences` 迁移到 `response_builder.py`；合并 `_ensure_content` / `_ensure_fallback_content`
- `session_memory/store_voiceprint.py`：`store_voiceprint_embedding` 拆为 `_update_embedding_record` / `_insert_embedding_record`

**验证**：
- `scripts/check_code_size.py`：>50 行函数 **25 个**（<40 目标达成，已无 >300 行文件）
- 相关聚焦测试通过：`tests/test_memory_channel.py`、`tests/test_admin_backends.py`、`tests/test_routes_admin_backends.py`、`tests/test_routes_device_voice_ws_helpers.py`、`tests/test_routes_chat_preflight.py`、`tests/test_chat_preflight_device.py`、`tests/test_routes_digital_human.py`、`tests/test_outcome_ledger.py`、`tests/test_device_policy*.py`、`tests/test_routes_chat_stream.py`、`tests/device_voice/test_asr_aliyun*.py`、`tests/test_routes_ws_voiceprint_helpers.py` 通过
- `ruff check .` / `pyright` 修改文件 clean

**预估工作量**：4 人天（分轮次）

---

### P2-2：`routes/v3_adapters.py` 重复 lazy import ✅ 已修复

**文件**：`routes/v3_adapters.py`

**问题**：原代码中多次重复 lazy import：
- `from routing_engine import classify_scenario` 出现 4 次
- `from lima_context import build_context_digest` 出现 3 次
- `from think_plan_context import enhance_coding_prompt, needs_plan` 出现 2 次

**修复方案**：将上述导入统一提取为模块顶层导入，各函数直接引用，不再重复 lazy import。

**验证**：`ruff check routes/v3_adapters.py` / `pyright routes/v3_adapters.py` clean；`tests/test_routes_v3_adapters.py` 11 passed；全量测试通过。

**预估工作量**：0.25 人天

---

### P2-3：Routes 跨层耦合 ✅ 已修复

**范围**：多个路由文件直接 import 底层模块（`health_tracker`、`backends_registry`、`http_caller`）

**修复方案**：
1. 新增 `routes/facade.py` 作为路由层与底层子系统（`backends_registry`、`health_tracker`、`http_caller`、`routing_executor`）之间的统一门面。
2. 路由文件统一通过 `routes.facade` 访问底层功能，不再直接 import 底层模块。
3. 已迁移的路由：
   - admin：`routes/admin_api.py`、`routes/admin_backends.py`、`routes/admin_extra_backend_edit.py`、`routes/admin_extra_config.py`、`routes/admin_extra_insights.py`
   - system：`routes/system_endpoints.py`
   - chat / eval / v3：`routes/chat_support.py`、`routes/eval_internal.py`、`routes/v3_adapters.py`

**验证**：
- `rg '^from backends_registry|^import backends_registry|^import health_tracker$|^import http_caller$' routes/` 仅剩 `routes/facade.py` 自身。
- 相关路由测试：`tests/test_routes_admin_api.py`、`tests/test_routes_admin_api_extra.py`、`tests/test_routes_admin_backends.py`、`tests/test_admin_backends.py`、`tests/test_routes_system_endpoints.py`、`tests/test_system_endpoints.py`、`tests/test_chat_support.py`、`tests/test_routes_chat_support.py`、`tests/test_routes_v3_adapters.py`、`tests/test_prefer_model_routing.py`、`tests/test_stream_routing_consistency.py` → 88 passed
- 全量 `.venv310/Scripts/python.exe -m pytest --tb=short -q`：**3531 passed, 17 skipped, 2 deselected**
- `ruff check routes/facade.py` 及迁移路由：通过；`pyright` 0 errors（1 处历史 warning 无关）

**预估工作量**：2 人天

---

### P2-4/P2-5：配置文件幻影路径 ✅ 已修复

**文件**：`pyrightconfig.json`、`ruff.toml`

**修复方案**：
- `pyrightconfig.json`：已删除 `search_gateway/` 等不存在路径。
- `ruff.toml`：已删除 `backends.py` 豁免及不存在 exclude 路径；已追加 `.venv310/`、`.test-tmp/`、`.pnpm-store/`。

**验证**：`ruff check .` 与 `pyright` 配置生效，无幻影路径报错。

**预估工作量**：0.25 人天

---

### P2-7/P2-8/P2-9：测试覆盖空白 ✅ 已修复（关键模块覆盖完成）

**范围**：
- `context_pipeline/` 17 模块零覆盖
- `session_memory/` 22 模块零覆盖（含 `redact.py` 脱敏）
- `routes/` ~55 模块零覆盖

**修复方案**：按优先级分批补充测试：
1. **第一批**（安全关键）：`session_memory/redact.py`、`context_pipeline/guardrails.py`、`context_pipeline/response_validator.py` ✅
2. **第二批**（核心路径）：`context_pipeline/code_context_injection.py`、`routes/chat_post_closeout.py`、`routes/chat_stream.py` ✅
3. **第三批**（管理面板）：`routes/admin_api.py`、`routes/admin_*.py` ✅
4. **第四批**（运维）：`routes/ops_metrics/`、`observability/` ✅

**已补充/扩展测试**：
- 第一批：`tests/test_session_memory_redact.py`、`tests/test_memory_redact.py`、`tests/test_context_pipeline_guardrails.py`、`tests/test_guardrails.py`、`tests/test_context_pipeline_response_validator.py`、`tests/test_response_validator.py`、`tests/test_session_memory_processor.py`、`tests/test_session_processor.py` → 133 passed
- 第二批：`tests/test_code_context_injection.py`（新建，9 用例）、扩展 `tests/test_routes_chat_post_closeout.py`（+12）、扩展 `tests/test_routes_chat_stream.py`（+2）
- 第三/四批：admin/ops/observability 相关测试集中运行 → 184 passed

**验证**：
- admin/ops/observability 集中测试：184 passed
- 全量 `.venv310/Scripts/python.exe -m pytest --tb=short -q`：**3550 passed, 17 skipped, 2 deselected**

**预估工作量**：10 人天（分批次，持续进行）

---

### P2-10：`time.time()` 导致的 flaky 测试 ✅ 已修复

**范围**：~10 个测试文件使用 `time.time()` 构造测试数据

**修复方案**：
- 安装 `freezegun` 依赖
- 使用 `@freeze_time("2026-06-22T12:00:00")` 固定时间
- 或使用 `monkeypatch.setattr("time.time", lambda: MOCK_NOW)` 模式

**预估工作量**：1 人天

---

### P2-11：误导性测试命名 ✅ 已修复

**文件**：`tests/test_routing_engine_integration.py` → `tests/test_route_result_dataclass.py`

**问题**：名为"路由引擎集成测试"，实际只测试 `RouteResult` dataclass 构造和字段访问。

**修复方案**：
- 已重命名为 `tests/test_route_result_dataclass.py`，文件内 docstring/类名同步更新为 "RouteResult dataclass construction"。
- 保留并精简了 `RouteResult` / `PickResult` 字段构造断言，补充 `PickResult` 必填字段测试。

**验证**：`tests/test_route_result_dataclass.py` 全部通过。

---

### P2-12：REST/WS/MQTT 三通道消息处理逻辑不统一 ✅ 已修复

**范围**：`routes/device_gateway.py`、`routes/device_gateway_ws.py`、`device_gateway/mqtt_client.py`

**问题**：`motion_event`、`device_info`、`self_check` 三种消息类型同时通过 REST、WebSocket、MQTT 三条通道处理，处理逻辑分散在不同模块，一致性无法保证。

**修复方案**：
- `record_motion_event_observability` 等处理逻辑已下放到 `device_gateway/task_lifecycle.py`。
- REST / WS / MQTT 通道统一调用 `device_gateway/task_lifecycle.py` 中的生命周期函数。
- 相关测试已同步修正 monkeypatch 目标。

**验证**：`tests/test_device_gateway_dispatch.py`、`tests/test_routes_device_gateway_dispatch.py`、设备生命周期测试全部通过。

**预估工作量**：2 人天

---

### P2-13：sync/async 桥接模式重复 ✅ 已修复

**文件**：`speculative_execution.py:57`、`device_gateway/task_creation.py:27`

**问题**：两处独立实现完全相同的 `_run_coro_sync()` 函数。

**修复方案**：
- 已提取公共实现到 `async_utils.py::run_coro_sync()`。
- `speculative_execution.py` 与 `device_gateway/task_creation.py` 均已改为 `from async_utils import run_coro_sync`。

**验证**：`ruff check` / `pyright` clean；相关测试通过。

**预估工作量**：0.5 人天

---

### P2-14：3 套 device store 模式重复 ✅ 已修复

**文件**：`device_gateway/store.py`、`device_ledger/store.py`、`device_memory/store.py`

**修复方案**：
1. 定义 `DeviceStoreBase` 抽象基类
2. 三套 store 继承基类，复用 `configure_from_env()` / `set_for_tests()` 模式
3. 统一 Redis 连接管理（已有 `redis_store_codec.py` 的 `connect_redis()` 作为基础）

**预估工作量**：1.5 人天

---

### P2-15：`context_pipeline/` 4+ 模块仅被测试引用 ✅ 已处理

**范围**：`event_log.py`、`retrieval_trace.py`、`production_index.py`、`graph_context_expander.py`

**修复方案**：与 P1-9 合并处理。

---

### P2-16/P2-17：HTTP 明文传输 ✅ 已修复

**范围**：社区后端 HTTP、VPS 内部代理 HTTP

**修复方案**：
- 在 `http_sync.py` 实现集中式 `_enforce_https_scheme(url, backend)` 门控。
- `http_sync.py` 的 `call_api` / `call_raw`、`http_async.py` 的 `call_api_async` / `call_raw_async`、`http_stream.py` 的 `call_api_stream` / `call_api_stream_async` 均在发起请求前调用门控。
- 规则：
  - `https://` 直接放行；
  - `http://localhost` / `http://127.0.0.1` 放行（本地调试）；
  - 其他 `http://` 默认拒绝，抛出 `BackendError(400)`；
  - 设置 `LIMA_ALLOW_HTTP_BACKENDS=1` 可显式放行，并记录 warning 日志。

**验证**：
- 新增 `tests/test_http_scheme_enforcement.py`，覆盖 `_enforce_https_scheme` 直接调用以及 sync/stream/async 调用路径的 scheme 拦截。
- 聚焦测试通过：`pytest tests/test_http_scheme_enforcement.py -q` 9 passed。

**预估工作量**：1.5 人天

---

### P2-18：缺少 CSP header ✅ 已修复

**文件**：`routes/security_headers.py`

**修复方案**：已添加 `Content-Security-Policy` header：`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'`。

**验证**：新增 `tests/test_security_headers.py` 覆盖 CSP 严格性；全量测试通过。

**预估工作量**：0.25 人天

---

### P2-19/P2-20：静默降级违反硬规则 ✅ 已修复

**范围**：7+ 个文件中 `logger.debug` 级别异常处理

**修复方案**：与 P1-4 合并处理，按文件逐个修复。

---

### P2-21：重复的复杂度评估逻辑 ✅ 已修复

**范围**：3 套独立的复杂度评估系统

**修复方案**：与 P1-10 合并处理。

---

## 6. P3 — 低优先级改善

### P3-1：`health_tracker.py` 导出私有全局变量 ✅ 已修复

**修复方案**：`health_tracker.py` 不再导出 `_cooldown_states`、`_health_map` 等私有变量。调用方直接从 `health_state.py` 导入。

**预估工作量**：0.5 人天

---

### P3-2：健康子系统模块碎片化

**修复方案**：审查 6 个健康模块的职责边界，合并职责重叠的模块。`health_state.py` 内部的 3 处 lazy import 循环依赖通过接口提取解决。

**预估工作量**：1 人天

---

### P3-3/P3-4：已落地的 Pipeline 模式（原描述有误） ✅

**说明**：经复核，`RequestContext` 与 `ResponsePipeline` 已在生产路径中使用，不属于未使用代码。原计划描述有误。

**证据**：
- `RequestContext` 被 `session_memory/processor.py:11`、`session_memory/prompt_recall.py:6,100` 直接导入并用于调用记忆处理器。
- `ResponsePipeline` / `ResponseContext` 被 `context_pipeline/response_processors.py:5,108,111` 定义，并在 `route_post_process.py:73-77` 的 `post_route` 中调用。

**结论**：Pipeline 模式已落地，无需删除。标记为完成并修正文档描述。

**预估工作量**：0.25 人天（复核+文档修正）

---

### P3-5：永远 skip 的死测试 ✅ 已修复

**修复方案**：`test_p1_4_device_stability_gate*.py` 中已无非条件 `@pytest.mark.skip` 的永远 skip 测试。`test_stability_loop` 为可选长稳态测试，通过 `--stability-rounds N` 启用，默认使用 `pytest.skip` 不干扰常规 CI。

**验证**：`pytest tests/test_p1_4_device_stability_gate*.py -q` 无 unconditionally skipped 用例。

**预估工作量**：0.1 人天

---

### P3-6/P3-8/P3-9：低质量测试改善 ✅ 已修复

**修复方案**：
- P3-6：`tests/test_pipeline_integration.py` 已补充 `select_backend_with_evolution`、`reflect_and_adjust`、`record_routing_outcome`、`get_metrics_snapshot` 等行为断言。
- P3-8：`tests/device_gateway_profile/` 中已无 `assert True` 占位断言；原有弱断言已替换为字段/行为验证。
- P3-9：`device_voice/` 测试断言密度已提升至 ≥0.5；持续补充中。

**验证**：聚焦测试通过；全量测试无回归。

**预估工作量**：1 人天

---

### P3-7：`test_triggers.py` 慢测试 ✅ 已修复

**修复方案**：`tests/xiaozhi_schema/test_triggers.py` 已使用可控 `_DatetimeClock` 重写，通过 SQLite `create_function("datetime", 1, clock)` 固定 `datetime('now')` 返回值，无需 `sleep(1.1)`。

**验证**：8 个 trigger 测试秒级完成，无 `time.sleep` 调用。

**预估工作量**：0.5 人天

---

### P3-10/P3-11：`pick_backend()` 和 `route()` 职责过多

**修复方案**：
- `pick_backend()` 拆分为 `_classify_and_recall()`、`_inject_contexts()`、`_select_and_enrich()` 三个子函数
- `route()` 的 12+ 隐式职责通过子模块已拆分，进一步优化为 Pipeline 模式（可选）

**预估工作量**：2 人天

---

### P3-12：重复的 complexity 评估 ✅ 已修复

**修复方案**：与 P1-10 合并处理。

---

### P3-13：speculative_execution 线程嵌套

**修复方案**：评估是否可将 `speculative_call` 改为纯 async 实现，消除 `_run_coro_sync`。需要分析调用方是否都在 async 上下文中。

**预估工作量**：2 人天（需深入分析）

---

### P3-14：SQLite 无连接池

**修复方案**：
1. 新建 `db_pool.py` 提供连接池
2. 或使用 `aiosqlite` 替代同步 `sqlite3`
3. 分阶段迁移 15+ 个独立连接点

**预估工作量**：3 人天（分阶段）

---

### P3-15：device_gateway 目录膨胀

**修复方案**：合并过度拆分的 task 模块（如 `task_deps.py` 18 行可合并到 `task_creation.py`）。目标从 54 文件降至 40 文件以下。

**预估工作量**：1 人天

---

### P3-16：Client Keys 仅内存存储 ✅ 已修复

**修复方案**：持久化到 SQLite 或 Redis，重启后恢复。

**预估工作量**：0.5 人天

---

### P3-17：paramiko 版本升级 ✅ 已修复

**修复方案**：`requirements_server.txt` 中 `paramiko>=3.4.0` 已改为 `paramiko>=3.5.0`。

**验证**：依赖解析通过；安全扫描无 paramiko 相关 CVE 告警。

**预估工作量**：0.1 人天

---

### P3-18：JDCloud 部署脚本清理 ✅ 已修复

**修复方案**：
- 经检查 `deploy/jdcloud/` 下已无重复脚本，仅保留 `deploy_jd.py`。
- 将硬编码 IP `117.72.118.95` 改为从环境变量 `JDCLOUD_HOST` 读取，默认回退原 IP。
- 用户名同样支持 `JDCLOUD_USER` 环境变量，默认 `root`。
- `.env.example` 增加 `JDCLOUD_HOST` / `JDCLOUD_USER` / `JDCLOUD_ROOT_PASSWORD` 示例。

**验证**：
- `ruff check deploy/jdcloud/deploy_jd.py` 通过
- `pyright deploy/jdcloud/deploy_jd.py` 0 errors（1 处历史 warning 无关）

**预估工作量**：0.5 人天

---

### P3-19/P3-20：小项修复

**修复方案**：
- P3-20（ruff exclude）：已更新 `ruff.toml`，排除 `.venv310/`、`.test-tmp/`、`.pnpm-store/`，并删除不存在路径。
- P3-19（合并 `task_deps.py`）：经评估，`device_gateway/task_deps.py` 作为测试 monkeypatch 入口被 5+ 测试文件依赖， intentionally 保留为 facade；记为 **保留（设计决策）**，不再合并。

**预估工作量**：0.25 人天

---

## 7. 改善路线图与里程碑

### 里程碑 R1：紧急修复（1 周）

**目标**：修复所有 P0 项，消除生产环境数据竞争和崩溃风险。

| 任务 | 预估 | 验收标准 |
|------|------|---------|
| P0-1 backend_reputation 线程安全 | 0.5d | 并发测试通过 |
| P0-2 MQTT 事件循环修复 | 0.5d | 无事件循环时不崩溃 |
| P0-3 Admin URL 验证 | 0.25d | 注入测试被拒绝 |
| P0-4 .gitignore 补全 | 0.1d | git status clean |
| P0-5 删除 `=6.0` | 0.05d | 文件不存在 |
| P0-6 网络测试隔离 | 0.5d | 无网络时 skip |
| P1-12 认证异常日志 | 0.25d | error 日志输出 |

**里程碑验证**：
- 全量 `pytest -q` 通过
- `ruff check .` clean
- 新增测试全部通过

---

### 里程碑 R2：安全加固（1.5 周）

**目标**：修复安全相关 P1 项，加固输入验证和错误处理。

| 任务 | 预估 | 验收标准 |
|------|------|---------|
| P1-1 SQLite 线程安全 | 1d | 并发写入完整性检查 |
| P1-3 routing_engine_context 日志提升 | 1d | warning 日志可见 |
| P1-4 88 处 except Exception 修复 | 2d | 无 debug-only 异常 |
| P1-11 HTTP 下载安全 | 0.5d | HTTPS + 校验 |
| P2-18 CSP header | 0.25d | header 存在 |
| P2-19/P2-20 静默降级修复 | 1d | warning 日志输出 |

---

### 里程碑 R3：测试补强（2 周）

**目标**：为核心执行路径和认证安全模块补充测试。

| 任务 | 预估 | 验收标准 |
|------|------|---------|
| P1-5 routing_executor 测试 | 3d | 50+ 用例 |
| P1-6 auth/safety 测试 | 2d | 30+ 用例 |
| P1-7 os.environ 清理 | 1d | 并行测试无冲突 |
| P2-10 time.time flaky 修复 | 1d | 5x 复跑稳定 |
| P2-11 误导性测试修复 | 0.5d | 重命名或补充 |
| P3-5/P3-6/P3-8 死测试清理 | 0.5d | 删除或修复 |

---

### 里程碑 R4：代码清理与配置统一（1.5 周）

**目标**：清理死代码、统一配置管理、修复配置不一致。

| 任务 | 预估 | 验收标准 |
|------|------|---------|
| P1-2 集中配置（阶段 1） | 1d | DB/Redis 配置统一 |
| P1-8 design_system.py 去重 | 0.5d | 仅 1 份副本 |
| P1-9 context_pipeline 死代码 | 0.5d | 4 模块删除 |
| P1-10 复杂度评估统一 | 1d | 单一实现 |
| P2-4/P2-5 配置幻影修复 | 0.25d | 无不存在路径 |
| P2-2 v3_adapters 修复 | 0.25d | 无重复 import |
| P3-3/P3-4 删除未使用 Pipeline | 0.25d | 代码删除 |

---

### 里程碑 R5：架构改善（2 周）

**目标**：改善模块耦合、接口设计、状态管理。

| 任务 | 预估 | 验收标准 |
|------|------|---------|
| P2-1 拆分 >50 行函数 | 4d | <40 个超标函数 |
| P2-3 Routes 跨层耦合 | 2d | facade 层建立 |
| P2-12 三通道统一 | 2d | 统一处理器 |
| P2-13 sync/async 工具统一 | 0.5d | 公共函数 |
| P2-14 device store 抽象 | 1.5d | 基类共享 |
| P3-1 health_tracker 封装 | 0.5d | 私有变量不导出 |
| P3-10 pick_backend 拆分 | 2d | 3 个子函数 |
| P3-15 device_gateway 瘦身 | 1d | <40 文件 |

---

### 里程碑 R6：测试覆盖扩展（持续）

**目标**：分批补充 context_pipeline、session_memory、routes 测试。

| 批次 | 预估 | 验收标准 |
|------|------|---------|
| 第一批（安全关键） | 2d | redact/guardrails/validator |
| 第二批（核心路径） | 3d | code_context/closeout/stream |
| 第三批（管理面板） | 2d | admin_*.py |
| 第四批（运维） | 3d | ops_metrics/observability |

---

## 8. 度量指标与验收标准

### 当前基线（2026-06-22）

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 全量测试 | 2402 passed / 19 skipped | 2500+ passed / <15 skipped |
| >300 行文件 | 0 | 0（保持） |
| >50 行函数 | 57 | <40 |
| 直接测试覆盖率 | 17.9%（94/524 模块） | >30%（>157 模块） |
| `except Exception: pass` | 0（核心路径） | 0（保持） |
| `except Exception: debug-only` | 88 处 | <10 处 |
| 环境变量读取分散度 | 496 处 / 148 文件 | <200 处 / <60 文件 |
| 死代码模块 | 4+ 个 | 0 |
| 重复代码块 | 3+ 个主要 | 0 |
| 无锁全局可变状态 | 1 个（backend_reputation） | 0 |
| `.gitignore` 遗漏 | 3 个目录 | 0 |

### 验收检查清单

每个里程碑完成后需验证：

- [ ] `python -m pytest --tb=short -q` 全量通过
- [ ] `ruff check .` clean
- [ ] `ruff format --check` clean
- [ ] `pyright`（修改文件）0 errors
- [ ] `scripts/check_code_size.py` 无新增违规
- [ ] `progress.md` 更新验证证据
- [ ] `findings.md` 更新缺陷状态
- [ ] `STATUS.md` 更新度量指标
- [ ] 相关聚焦测试 5x 复跑稳定

### 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 集中配置改造影响范围大 | 分 3 阶段，每阶段独立验证 |
| routing_executor 测试需要 mock 大量依赖 | 优先 mock HTTP 层，使用真实 RouteResult |
| 死代码删除可能影响 lazy import | CodeGraph + ripgrep 双重确认 |
| 线程安全修复可能改变并发行为 | 新增并发测试 + 线程安全分析 |
| 测试清理可能暴露隐藏 bug | 逐个审查 skip 原因，不盲目删除 |

---

## 附录：分析工具与命令

```bash
# 代码尺寸检查
python scripts/check_code_size.py

# 死代码审计
python scripts/codegraph_orphans.py --fanin

# 静默降级扫描
rg "except Exception.*pass|except.*pass" --type py -l

# 环境变量分散度统计
rg "os\.getenv|os\.environ" --type py -c | sort -t: -k2 -rn | head -20

# 全量测试
python -m pytest --tb=short -q

# 代码审查
ruff check .
ruff format --check
pyright <modified_files>
```

---

> 本文档为改善计划的权威参考。执行时按里程碑顺序推进，每个里程碑完成后更新 `progress.md` 和 `findings.md`。
