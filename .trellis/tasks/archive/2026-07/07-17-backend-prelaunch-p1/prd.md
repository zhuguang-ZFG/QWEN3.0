# 后端预发布 P1 加固

## Goal

在单实例 + Redis task store + production runtime 下，落地预发布 P1 上线加固子集，降低：legacy JWT 缺 `typ`、Voice ASR start 失败仍烧票、幂等 Redis 抖动 fail-open、限流误关、SQLite 锁、MCP 空 token 静默 401、Status 未知终态误报 completed。

## Background

- 来源：2026-07-17 后端预发布深度审查 P1；用户选范围 **S**，JWT 策略 **F**，Voice 设备 **O**，Status 未知 **N**。
- 多实例 WS ticket/槽位迁 Redis 为独立 P0，不在本任务。
- `make_token` 已发 `typ=device`；无 `typ` 仅旧会话。Voice `device_id` 文档/测试均为可选。

## Requirements

| ID | 要求 | 锚点（现状） |
|----|------|----------------|
| R1 | `LIMA_JWT_REQUIRE_TYP`：生产默认开，拒无 `typ` 的 device JWT；非生产默认关 | `device_logic/auth.py:109-110` |
| R2 | Voice：`device_id` 保持可选；有则须 `require_device_control`（回归） | `routes/device_app_voice_ws.py:72-78` |
| R3 | ASR `session.start()` 成功后才 consume ticket；失败不烧票 | `routes/device_app_voice_ws.py:249-257` |
| R4 | 生产 + Redis 不可用/SET 失败：带 Idempotency-Key 的 dispatch → 503，不 fail-open | `dlc_api/idempotency.py:117-125` + `dlc_api/routes.py:174-175` |
| R5 | LiMa SQLite 新建连接：`journal_mode=WAL` + `busy_timeout` | `config/sqlite_pool.py:45` |
| R6 | 生产忽略 `LIMA_RATE_LIMIT_DISABLE` | `config/settings_core.py:44` |
| R7 | 非 loopback `DLC_API_URL` 且 `DLC_API_TOKEN` 空 → MCP `main` 启动失败 | `dlc_mcp/server.py:16-26,272` |
| R8 | Status 未知/查不到终态：**不推** terminal；打 warning | `routes/device_app_status_ws.py:140` |

## Out of scope

- Voice 强制必填 `device_id`；WS ticket/槽位 Redis；图库 token 出 query；env-token fallback 运维清单；query-auth 硬关；跨 worker dispatch 锁；真机/提审/固件/小程序 UI。

## Acceptance Criteria

- [x] AC1：生产门禁开时无 `typ` → 401；非生产默认仍兼容（可测 flag）
- [x] AC2：`session.start` 失败路径 ticket 未 consume（pytest）；成功路径 consume
- [x] AC3：生产 mock Redis down + Idempotency-Key → 503（或等价 failed/unavailable），非 duplicate 放行
- [x] AC4：sqlite 连接后 PRAGMA WAL 可测；busy_timeout 已设
- [x] AC5：生产下 `RATE_LIMIT_DISABLE=1` 仍限流
- [x] AC6：MCP 非 loopback + 空 token → `main` 非零退出或显式 raise
- [x] AC7：未知终态不发送 `task_completed`
- [x] AC8：`docs-site/api/voice.md` 烧票语义改为 start 成功后消耗；device_id 仍标注可选
- [x] AC9：相关 pytest + `ruff check` + 改动文件代码尺寸门禁通过

## Decisions

- **S**：MVP 子集（非全量 P1）。
- **F**：JWT 用 `LIMA_JWT_REQUIRE_TYP`，生产默认开。
- **O**：Voice 不强制 device_id。
- **N**：Status 未知不推 terminal。

## Notes

- 实现前需用户确认本 PRD + `design.md` + `implement.md`，再 `task.py start`。
