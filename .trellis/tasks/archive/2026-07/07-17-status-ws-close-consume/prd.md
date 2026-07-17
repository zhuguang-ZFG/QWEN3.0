# Status WS finalize close + consume_if（深度 review P2/P3）

## Goal

对齐 Voice WS 已修模式：Status WebSocket pre-accept 失败 close code 不被 finalize 无码覆盖；`app_status_ws_ticket` 增加 `consume_if` 对称 Voice。

## Requirements

### R1 — finalize 不覆盖 intentional close code

- consume 失败已 `close(1008)` 时，finalize **不得**无码 `close()` 覆盖。
- post-accept 正常结束：finalize 仍可在 `CONNECTED` 时补 close。

### R2 — consume_if 对称 Voice

- predicate 失败时不 pop ticket。
- `_consume_status_ticket_if_present` 改用 `consume_if`。

## Out of Scope

- R3 task_completed vs task_failed
- Voice ASR pre-accept 创建时机
- MCP `isError`（需 xiaozhi.me E2E）
- 多 worker Redis ticket

## Acceptance Criteria

- [x] `_finalize_status_ws` 仅在 `application_state == CONNECTED` 时 close
- [x] `consume_if` 单测：predicate 失败 ticket 仍可 peek
- [x] consume 失败 close code 回归测试 `[1008]`
- [x] 现有 status/ticket pytest 全绿；ruff 通过
