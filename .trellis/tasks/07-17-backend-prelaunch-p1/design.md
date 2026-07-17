# Design — 后端预发布 P1 加固

## Boundaries

| 模块 | 改动 | 不改 |
|------|------|------|
| `device_logic/auth.py` + settings | typ 门禁 | admin_auth legacy（本任务可不强制对称，或同 flag 镜像——见下） |
| `routes/device_app_voice_ws.py` | consume 移到 start 成功后 | ticket 存 Redis |
| `dlc_api/idempotency.py` + `routes.py` | 生产 fail-closed | L1 结构重写 |
| `config/sqlite_pool.py` | 新连接 PRAGMA | 换 DB 引擎 |
| `config/settings_core.py` / rate 读取点 | 生产忽略 disable | Redis 限流迁移 |
| `dlc_mcp/server.py` | 启动校验 | MCP 协议字段 |
| `routes/device_app_status_ws.py` | 未知不推送 | 新事件类型 |
| `docs-site/api/voice.md` | 烧票语义 | 改必填 device |

**admin JWT**：`admin_auth` 同样有 legacy no-typ。为对称与安全，**同一 `LIMA_JWT_REQUIRE_TYP` 生产默认开时一并拒绝 admin 无 typ**（小增量，避免半开）。

## Contracts / data flow

### JWT (R1)

```
decode → typ==admin? reject
      → typ is None?
           require_typ? → 401
           else warning + continue
```

`require_typ = env LIMA_JWT_REQUIRE_TYP` 显式 0/1；未设时 `is_production_runtime()` → True。

### Voice burn (R3)

```
peek/auth → validate ASR → slot
  → accept
  → open session → start()
  → start OK: consume_if; fail → close 4401 + teardown
  → start fail: close 1011, no consume
```

**竞态**：同 ticket 双连可能在 consume 前各 start 一次 ASR；概率低（密钥+TTL），接受并在注释说明。不引入 hold 锁。

### Idempotency (R4)

- 新增 `IdempotencyUnavailableError`（或返回三态）；生产且 Redis 客户端缺失 / SET 抛错 → raise。
- `routes.dispatch`：捕获 → `JSONResponse(503)` 或 `TaskDispatchResponse(status="failed", error="idempotency store unavailable")`（与现有 API 风格对齐，优先 503 + 明确 error）。
- 非生产：保持现 fail-open + L1。

### SQLite (R5)

在 `sqlite_pool` **新建** `connect` 后执行：

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

池复用连接不重复设（已生效）。

### Rate limit (R6)

`rate_limit_disable` 生效处（settings 属性或 `SECURITY.rate_limit_disable` 读取包装）：若 `is_production_runtime()` 则视为 False。避免散落多处时，优先 **单一 accessor**（若已有则改一处）。

### MCP (R7)

`main()` 入口：若 `_is_remote_dlc_api(DLC_API_URL)` 且非空 token 缺失 → `logger.error` + `sys.exit(1)`。
loopback（`127.0.0.1` / `localhost` / `::1`）允许空 token（本地联调）。

### Status (R8)

`_resolve_task_terminal_event` → `str | None`；未知返回 `None`；调用方仅在非 None 时 `send_json`。

## Compatibility

- 生产旧无 typ JWT：需重新登录（F 已知代价）。
- Voice 无 device_id：不变（O）。
- Status 客户端：未知场景少一次事件，优于假 completed（N）。
- Idempotency 503：客户端应重试；与 duplicate 区分。

## Rollback

- 旗标：`LIMA_JWT_REQUIRE_TYP=0` 紧急关 typ 门禁。
- 其余逻辑改可单 commit revert；无 schema 迁移。

## Trade-offs

| 选择 | 取舍 |
|------|------|
| start 后 consume | 防烧票 vs 双连双 start 窗口 |
| 生产幂等 503 | 拒重复风险 vs Redis 抖动时短时不可 dispatch |
| Status 不推送 | 无假成功 vs 客户端可能空等（可用 REST 查） |
