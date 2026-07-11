# LiMa 优化实施计划（2026-07-11）

> 来源：MiMo 调研 → Kimi + Atom 双重代码核对 → Claude Code plan 设计。本文以核对后的现状为准。

## 执行状态（2026-07-12 更新）

- **A 完成**：中间件恒启用（`server_dlc.py:68`）。原计划的 `LIMA_REQUEST_ID_MIDDLEWARE` 关闭开关**未实现且决策删除**（YAGNI：开销可忽略，关掉会断日志关联，无禁用场景）。
- **B 完成**：`LIMA_STRUCTURED_LOGGING=1` 启用（`server_dlc.py:29`）；fallback `basicConfig` 在 `:31`。
- **C 完成验证后删除**：VPS 模块级验证全 PASS，但发现 `check_rate_limit` 生产零调用方（keyed 限流已覆盖生产需求），按 ponytail 删除实现与测试（commit `7eed9aac`）。
- **D 完成**：`LIMA_REDIS_TASK_INDEX` 经 VPS 模块级验证全 PASS（索引写入/索引读路径/TTL/开关行为）。
- **E 三态**：代码原语完成（`try_backends` + `LIMA_AUTO_FALLBACK`）/ **draw 已接线**（`device_draw_handler._generate_image`，`idempotent=True`；voice 不适用）/ ESP32 E2E 待排期。

## 整体排序与依赖

```
A (X-Request-ID) → B (结构化日志，依赖 A 的 request_id)
                 ↘
C (IP 限流 Redis 化，独立于 A/B，可并行)
                  ↘
D (Redis 任务索引，独立于 A/B/C，可并行)

E (AI fallback 路由，独立；建议 B 完成后做，便于 warning 可观测)
```

- 必须串行：A → B（B 的 JsonFormatter 绑定 request_id，依赖 A 注入 context）。
- 可并行：C、D 互不依赖；E 与 C/D 无代码交叉。

## 已核实现状（证据）

> 以下为 2026-07-11 实施前快照；以顶部「执行状态」为准。

- `device_gateway/redis_store.py:80,102` 两处 `hgetall(self._key("tasks"))` 全量反序列化后按 `device_id` 过滤；`list_tasks_for_device` 的 limit 为遍历后截断（:123-124）。真实 O(N)。
- `device_gateway/sessions.py:62/65/68` `SessionRegistry`、`_MAX_DEVICE_SESSIONS=2000`、进程内 `dict`+`RLock`；`remove_zombies`(:139) 已调 `requeue_pending_tasks`。
- `rate_limiter.py`：keyed 限流已有完整 Redis backend（`_check_keyed_redis` incr+expire）；`check_rate_limit`（IP 滑动窗口 :134-152）纯内存。
- `device_gateway/model_routing.py:62` `get_route_role_alternatives` 仅返回列表，无自动 fallback（已过时，见执行状态）；`device_draw_handler.py:104` 注释「image_fallback 已删除」。
- ASR：`.env.example:269-271` 有 `aliyun_fallback`，但 `asr_composite.py` 已删，`device_voice/providers/registry.py:22` 把它当 `dashscope` 别名，`create_asr_provider()` 只返单一 provider。
- `server_dlc.py:25` 仍是 `logging.basicConfig`（已过时，见执行状态）；`observability/` 仅 `correlation.py`（内存 ring buffer）+ 4 个 prometheus 模块；无 structured_logging.py（已过时，见执行状态）；无 OTel。
- `Dockerfile:29` 单 uvicorn，无 `--workers`。
- `dlc_api/middleware.py` 仅 `BodySizeLimitMiddleware`，无 X-Request-ID（已过时，见执行状态）。
- 可复用设计：`docs/OBSERVABILITY_EVENTS_CN.md:4`、`docs/archive/strategic-plans-2026-06/OPTIMIZATION_ANALYSIS_2026-06-23.md:127-128`。

## 条目明细

### A. X-Request-ID 中间件（0.5d）
- 文件：`dlc_api/middleware.py`（追加 `RequestIDMiddleware(BaseHTTPMiddleware)`）、`server_dlc.py`（注册）。
- 逻辑：读 `X-Request-ID`，无则 `uuid4().hex[:16]`；存 `request.state.request_id` + contextvars；响应头写回。`add_request_id_middleware(app)`。
- 测试 `tests/test_request_id_middleware.py`：① 无 header 自动生成 ② 有 header 透传 ③ `/health` 带 header ④ 并发不串。
- env：~~`LIMA_REQUEST_ID_MIDDLEWARE=0` 可跳过（默认启用）~~ 开关未实现，2026-07-12 决策删除（见顶部执行状态）：中间件恒启用。
- 完成定义：`curl -v /health` 返回 `X-Request-ID`；CI 绿。

### B. 结构化日志（1d）
- 文件：新建 `observability/structured_logging.py`；改 `server_dlc.py:25`。
- API：`setup_structured_logging(*, service, version)`；`JsonFormatter` 输出 JSON-line；`QueueHandler`+`QueueListener`+`RotatingFileHandler(maxBytes=50MB, backupCount=5)`；`atexit.register(listener.stop)`，listener daemon。
- 绑定：`timestamp/level/logger/message/request_id(contextvars)/service/version/extra`。日志文件 `logs/dlc.jsonl`，同时输出 stderr（Docker logs）。
- env：`LIMA_STRUCTURED_LOGGING=1` 启用；`=0`（默认）保持 basicConfig。
- 测试 `tests/test_structured_logging.py`：JSON 格式 / request_id 绑定 / rotation / 开关为 0 不改原行为 / QueueHandler 不阻塞。
- 完成定义：开关打开后 `logs/dlc.jsonl` 每行可被 `json.loads` 解析；request_id 与 A 一致。

### C. IP 限流 Redis 化（1d）
- 文件：`rate_limiter.py`（改 `check_rate_limit`，抽 `_check_ip_redis`）。
- 方案：Sorted Set `lima:ip_rate:{ip}`，`ZADD`+`ZREMRANGEBYSCORE`+`ZCARD`，TTL=window×2。
- 降级：Redis 异常 → `logger.warning("IP rate-limit Redis fallback: %s", err)` → 走内存（已有，非静默）。
- env：`LIMA_IP_RATE_REDIS=1`（默认 0 纯内存）。
- 测试 `tests/test_rate_limiter_redis.py`：正常 sorted set / 断连降级+warning / 窗口过期 / multiplier / 多 worker 共享（`@pytest.mark.redis`）。
- 完成定义：开关开 + Redis 正常，两 uvicorn 进程计数统一；Redis 断 warning 可见且服务不中断。**需 VPS 真实验证。**

### D. Redis 任务二级索引（2-3d）
- 文件：`device_gateway/redis_store.py`（核心），可选 `device_gateway/task_index.py`。
- 结构：每 device 一个 Set `lima:task_idx:{device_id}` 成员为 task_id；写 `SADD`，完成/删 `SREM`；查 `SMEMBERS`→批量 `HMGET`。
- 过渡：**双写**（无论开关都维护索引 Set，幂等 SADD）+ **读切换**（开关控读路径）；回退=关开关。写操作 pipeline 原子化；后台 reconcile 每 5min 对账 + `logger.warning` 报告差异。
- env：`LIMA_REDIS_TASK_INDEX=1`（默认 0 走 hgetall）。
- 测试 `tests/test_redis_task_index.py`：写自动建索引 / 完成移除 / 索引模式与 hgetall 结果一致 / 孤儿自愈 / 性能 benchmark（非 CI 必须）。
- 完成定义：100 设备×50 任务 P99 < 5ms（hgetall 约 50ms+）；双写无显著延迟；关开关行为不变。**需 VPS 真实验证。**

### E. AI Provider 自动 Fallback 路由（2d）
- 文件：`device_gateway/model_routing.py` 新增；调用方 `device_draw_handler.py`、`device_voice/` handler。
- API：`async def try_backends(route_role, execute_fn, *, idempotent=False) -> T`，按 `DEVICE_ROLE_PREFERENCES` 顺序尝试。
- 逻辑：成功即返；失败时 `idempotent=True`→`logger.warning`+继续下一个；`idempotent=False`（绘画）→`logger.warning`+**仅转 `safe_retry=True` 备选**，无则 raise 原异常。单次 backend timeout 防累加。
- env：`LIMA_AUTO_FALLBACK=1`（默认关，退化为只调首选）。
- 测试 `tests/test_fallback_routing.py`：首选成功不触发 / 首选失败+idempotent→依次 / 首选失败+非幂等无 safe 备选→raise / 每次 fallback 有 warning / 全失败返最后异常。
- 完成定义：文本/ASR 首选不可用自动切换（日志可见）；绘画不盲重试。**需 ESP32 触发 draw task 端到端验证。**

## 不做清单（与硬规则冲突或 ROI 不足）

| 项 | 理由 |
|---|---|
| 多 worker + 会话外部化 | 单 worker 足够；外部化涉 Redis pub/sub + 协议改动 |
| OpenTelemetry | structlog + Prometheus 已覆盖；SDK 偏重 |
| 独立 AI 网关进程（LiteLLM/Portkey） | 增加部署复杂度，内聚路由足够 |
| 重建 ASR composite fallback | 已删；统一由 E 的 `try_backends` 覆盖 |
| K8s / Helm | 单 VPS + Docker Compose 足矣 |
| uvicorn `--workers` | 需先解决 SessionRegistry 共享，属外部化前置 |

## 门禁命令

- 聚焦：`pytest tests/<对应> -v`、`ruff check <改动文件>`、`pyright <改动文件>`
- 全量：`python scripts/run_pre_commit_check.py --full`
- 代码量：`python scripts/check_code_size.py`

## 估算

总计 **6.5–7.5 人天**；建议 A+B 串行一人，C+D+E 一人按序；约 4 个工作日完成开发+单测，额外 1–2 天 VPS 集成验证。

## 硬规则约束

禁止静默降级（降级/失败转移须 `logger.warning`）；禁止硬编码 secret；`.env` 只合并不覆盖；单文件 ≤300 行 / 单函数 ≤50 行；ruff py310 行宽 120；pyright；pytest asyncio_mode=auto；增量、可灰度、可回退；绘画任务非幂等不可盲重试。
