# V3 迁移集成方案

> 创建时间: 2026-05-20
> 状态: 设计中
> 目标: 将 17 个 V3 模块接入 server.py，替换 smart_router 生产路径

---

## 1. 当前问题清单

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| P1 | server.py 仍 100% 走 smart_router，V3 模块零接入 | CRITICAL | 新代码全是死代码 |
| P2 | BACKENDS 字典在 smart_router.py 和 backends.py 双份维护 | HIGH | 新增后端必须改两处 |
| P3 | server.py 内联流式逻辑有已知 bug（异常吞掉/线程泄漏） | HIGH | 生产稳定性 |
| P4 | vision_handler/orchestrate 直接 import smart_router | HIGH | 绕过 V3 健康追踪 |
| P5 | key_pool/probe_loop/semantic_cache 无启动入口 | MEDIUM | 功能缺失 |
| P6 | v3_integration.py 与 routing_engine.py 功能重叠 | MEDIUM | 维护混乱 |
| P7 | deploy_v3.py 明文硬编码服务器密码 | HIGH | 安全隐患 |
| P8 | fallback_chain.quality_check 无调用点 | LOW | 死代码 |
| P9 | stats_collector 和 fallback_chain 重复定义 FALLBACK_LOG | LOW | 双源 |

---

## 2. 目标架构

```
server.py (瘦入口, <800行目标)
  ├── FastAPI app + 路由注册
  ├── 请求解析 + 参数提取
  └── 调用 routing_engine.route() / streaming.speculative_stream()

routing_engine.py (统一路由, 保留)
  ├── classify → select → inject → execute → respond
  └── call_fn 由 server.py 注入

http_caller.py (新建, 从 smart_router 提取)
  ├── call_api(backend, messages, max_tokens) → str
  ├── call_api_stream(backend, messages, max_tokens) → Generator
  └── 使用 key_pool.get_key() 获取密钥

streaming.py (已提取, 待接入)
  ├── bridge_stream(call_stream_fn, ...) → Generator
  └── speculative_stream(predict_fn, route_fn, ...) → Generator

辅助模块 (已就绪):
  health_tracker / sticky_session / key_pool / probe_loop
  semantic_cache / skills_injector / response_builder
  fallback_chain / stats_collector / vision_handler / tool_handler
```

**删除清单:**

| 文件/代码 | 动作 | 原因 |
|-----------|------|------|
| `v3_integration.py` | 删除 | 被 routing_engine.py 完全覆盖 |
| `smart_router.BACKENDS` | 删除 | 统一到 backends.py |
| `smart_router.route/analyze/select_backend` | 删除 | 被 routing_engine 替代 |
| `smart_router.cb_allow/cb_record` | 删除 | 被 health_tracker 替代 |
| `server.py: _real_stream_chunks` | 删除 | 被 streaming.bridge_stream 替代 |
| `server.py: _speculative_stream_chunks` | 删除 | 被 streaming.speculative_stream 替代 |
| `backends.py: ROUTE 字典` | 删除 | V3 用 POOLS 替代意图路由 |

**保留（smart_router.py 瘦身后剩余）:**

| 函数 | 原因 | 最终归宿 |
|------|------|----------|
| `call_api()` | 同步 HTTP 调用核心 | → http_caller.py |
| `call_api_stream()` | 流式 HTTP 调用核心 | → http_caller.py |
| `clean_response()` | 响应清洗 | → response_builder.py |

---

## 3. 迁移阶段

### Phase 1: 提取 HTTP 调用层（解决 P2）

**目标:** 新建 `http_caller.py`，从 smart_router 提取 call_api/call_api_stream

**约束:**
- 所有后端配置只从 `backends.py` 读取，smart_router.BACKENDS 标记 deprecated
- `http_caller.call_api(backend_name, messages, max_tokens)` → str
- `http_caller.call_api_stream(backend_name, messages, max_tokens)` → Generator[str]
- 集成 `key_pool.get_key(provider)` 替代硬编码 key 查找
- 错误时调用 `health_tracker.record_failure()`

**文件变更:**
```
新建: http_caller.py (~150行)
修改: backends.py — 删除 ROUTE 字典
修改: smart_router.py — call_api/call_api_stream 改为 import http_caller 的 wrapper
```

### Phase 2: server.py 接入 routing_engine（解决 P1, P3）

**目标:** server.py 的主路由路径切换到 routing_engine

**约束:**
- 非流式请求: `routing_engine.route(query, messages, call_fn=http_caller.call_api)`
- 流式请求: `streaming.speculative_stream(predict_fn, route_fn, call_stream_fn)`
- 删除 `_real_stream_chunks` 和 `_speculative_stream_chunks` 内联代码
- 保留 smart_router 作为 fallback（routing_engine 异常时降级）
- 接入 `stats_collector.record_request()` 记录每次请求

**切换策略（灰度）:**
```python
USE_V3 = os.environ.get("LIMA_V3", "1") == "1"

if USE_V3:
    result = routing_engine.route(...)
else:
    result = smart_router.route(...)  # legacy fallback
```

**文件变更:**
```
修改: server.py — 替换路由调用，删除内联流式代码
删除: v3_integration.py — 功能已合并到 routing_engine.py
```

### Phase 3: 辅助模块接入（解决 P4, P5）

**目标:** vision_handler/orchestrate 切换到 V3；启动 probe_loop/key_pool/semantic_cache

**约束:**
- `vision_handler.py` 删除 `import smart_router`，改用 `http_caller.call_api` + `health_tracker`
- `orchestrate.py` 的 `smart_router.route()` 调用改为 `routing_engine.route()`
- FastAPI lifespan 事件中启动 `probe_loop.start(probe_fn=http_caller.probe)`
- `routing_engine.execute()` 前检查 `semantic_cache.get(key)`，成功后 `semantic_cache.put(key, answer)`
- `key_pool` 在 `http_caller` 内部使用，对外透明

**文件变更:**
```
修改: vision_handler.py — 替换 smart_router 依赖
修改: orchestrate.py — 替换 smart_router 依赖
修改: server.py — lifespan 中启动 probe_loop
修改: routing_engine.py — 接入 semantic_cache
```

### Phase 4: 清理与安全（解决 P6, P7, P8, P9）

**目标:** 删除冗余代码，修复安全问题

**约束:**
- 删除 `v3_integration.py`（Phase 2 已完成替换）
- `smart_router.py` 瘦身至 <200 行（仅保留暂未迁移的边缘逻辑）
- `deploy_v3.py` 密码改为 `os.environ["LIMA_DEPLOY_KEY"]`，使用 SSH key 认证
- `fallback_chain.py` 的 `FALLBACK_LOG` 统一到 `stats_collector.FALLBACK_LOG`
- `fallback_chain.quality_check()` 接入 `routing_engine.execute()` 的返回值校验

**文件变更:**
```
删除: v3_integration.py
修改: smart_router.py — 大幅瘦身
修改: deploy_v3.py — 移除硬编码密码
修改: fallback_chain.py — 删除重复常量
修改: routing_engine.py — 接入 quality_check
```

---

## 4. 模块接口契约

### http_caller.py（新建）

```python
def call_api(backend: str, messages: list[dict], max_tokens: int = 4096,
             *, timeout: int = None) -> str:
    """同步调用后端 API，返回纯文本响应。失败抛异常。"""

def call_api_stream(backend: str, messages: list[dict], max_tokens: int = 4096,
                    *, timeout: int = None) -> Generator[str, None, None]:
    """流式调用后端 API，yield 每个 chunk 的文本。"""

def probe(backend: str) -> bool:
    """发送 max_tokens=1 的探活请求，返回是否成功。"""
```

### routing_engine.route()（已有，微调）

```python
def route(query: str, messages: list[dict], *,
          fmt: str = "openai", ide_source: str = "",
          model: str = "", max_tokens: int = 4096,
          system_prompt: str = "", headers: dict = None,
          call_fn: Callable = None,
          cache_enabled: bool = True) -> RouteResult:
    """
    统一路由入口。
    新增 cache_enabled 参数控制 semantic_cache 是否生效。
    call_fn 签名: (backend, messages, max_tokens) -> str
    """
```

### streaming.speculative_stream()（已有，确认接口）

```python
def speculative_stream(
    predict_fn: Callable[[], str],        # 快速预测后端
    route_fn: Callable[[], str],          # 完整路由（可能慢）
    call_stream_fn: Callable[[str], Generator],  # 流式调用
    messages: list[dict],
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """投机流式：先用 predict 开始流，route 完成后决定是否切换。"""
```

---

## 5. 灰度与回滚策略

### 环境变量控制

```bash
LIMA_V3=1          # 启用 V3 路由（默认开）
LIMA_V3=0          # 回退到 smart_router
LIMA_CACHE=1       # 启用 semantic_cache
LIMA_PROBE=1       # 启用 probe_loop
LIMA_SKILLS=1      # 启用 skills 注入
```

### 回滚步骤

1. SSH 到服务器
2. `export LIMA_V3=0`
3. `kill -HUP $(pgrep -f uvicorn)` — 优雅重载
4. 验证 `/health` 返回正常

### 监控指标

| 指标 | 正常范围 | 告警阈值 |
|------|----------|----------|
| 请求成功率 | >95% | <90% |
| P95 延迟 | <5s | >10s |
| fallback 触发率 | <20% | >40% |
| 熔断后端数 | <3 | >5 |

---

## 6. 实施顺序与依赖

```
Phase 1 (http_caller)
    │
    ├── 无外部依赖，可立即开始
    │
    v
Phase 2 (server.py 接入)
    │
    ├── 依赖 Phase 1 完成
    ├── 这是最高风险步骤，需要完整测试
    │
    v
Phase 3 (辅助模块)
    │
    ├── 依赖 Phase 2 完成
    ├── 可并行处理 vision/orchestrate/probe/cache
    │
    v
Phase 4 (清理)
    │
    └── 依赖 Phase 2+3 完成且生产稳定运行 >24h
```

---

## 7. 测试要求

### 每个 Phase 完成后必须通过

| 测试类型 | 覆盖 | 工具 |
|----------|------|------|
| 单元测试 | 新模块所有公开函数 | pytest |
| 集成测试 | routing_engine + http_caller 端到端 | pytest + mock server |
| 冒烟测试 | curl 真实请求到本地 server | curl / httpie |
| IDE 测试 | Claude Code + Cursor 连接 | 真实 IDE |

### Phase 2 额外要求

- 对比测试：同一组请求分别走 V3 和 legacy，验证结果一致性
- 压力测试：10 并发请求持续 60s，无内存泄漏、无线程泄漏

---

## 8. 不做的事（明确排除）

| 排除项 | 原因 |
|--------|------|
| 重写 smart_router 的 HTTP 调用为 httpx async | 风险太大，先提取再替换 |
| 合并 server.py 的两个端点为一个 | 协议差异大，强合并增加复杂度 |
| 引入 Redis 做分布式状态 | 当前单机足够，过早优化 |
| 重构 orchestrate.py 的多步编排逻辑 | 不在本次范围，先接入 V3 即可 |
| 修改 skills 文件内容 | 内容层面独立迭代，不阻塞架构迁移 |

---

## 9. 验收标准

迁移完成的定义：

- [ ] `server.py` 不再直接调用 `smart_router.route/analyze/select_backend`
- [ ] 所有后端配置仅存在于 `backends.py`，单一来源
- [ ] 流式请求通过 `streaming.py` 处理（无内联流式代码）
- [ ] `probe_loop` 在服务启动时自动运行
- [ ] `LIMA_V3=0` 可立即回退到旧路径，无需改代码
- [ ] 48+ 现有测试继续通过
- [ ] 新增 http_caller 单元测试覆盖 call_api / call_api_stream / probe
- [ ] Claude Code + Cursor 端到端连接正常（真实 IDE 测试）
- [ ] `deploy_v3.py` 不含明文密码
- [ ] `smart_router.py` 行数 <500（仅保留 legacy fallback wrapper）
