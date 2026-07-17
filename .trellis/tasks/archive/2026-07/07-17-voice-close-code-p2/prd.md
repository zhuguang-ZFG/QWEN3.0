# Voice WS finalize close code（深度 review P2）

## Goal

修复深度 code review 遗留 P2：Voice WebSocket 在 **pre-accept 失败**（consume 竞态 4401、ASR start 失败 1011）后，`finally` 中 `_finalize_voice_session` 的无码 `close()` 可能覆盖已发送的 intentional close code。

## Background

- 父任务 `07-17-ws-ticket-status-p2` 已实现延迟 consume + session 泄漏修复（`1abc9c42`）。
- 深度 review 发现：`_finalize_voice_session` 在 `application_state != DISCONNECTED` 时调用默认 `close()`（code=1000），若 Starlette/mock 在 `close(4401)` 后仍停在 `CONNECTING`，会二次 close 覆盖 4401/1011。

## Requirements

### R1 — finalize 不覆盖 intentional close code

- pre-accept 失败路径已 `close(4401)` / `close(1013)` / ASR start 失败已 `close(1011)` 时，finalize **不得**再发无码 `close()`。
- post-accept 正常结束：finalize 仍可在 `CONNECTED` 时补默认 close。

### R2 — 回归测试断言 close code

- consume 竞态失败：`ws close codes == [4401]`，且 DashScope session 仍被 `close()`。
- ASR start 失败：`ws close codes == [1011]`，session 仍被清理。

## Out of Scope

- Status WS `consume_if` CAD（P3）
- Buffered session 双 `finish()`（P3）
- R3 status `task_completed` vs `task_failed`
- 真机 HIL / fz agent_gate（无 G-code 变更）

## Acceptance Criteria

- [x] `_finalize_voice_session` 仅在 `CONNECTED` 时补 `websocket.close()`
- [x] `test_consume_race_abandons_dashscope_session` 断言 `ws_codes == [4401]`（FakeWs 保持 CONNECTING 作回归护栏）
- [x] `test_dashscope_start_fail_keeps_close_1011` 断言 `ws_codes == [1011]`
- [x] `tests/test_device_app_voice_ws_ticket_burn.py` 全绿；`ruff check` 通过
- [x] 无新增静默 `except: pass`；改动文件仍 ≤300 行

## Notes

- Lightweight task：PRD + implement 即可；无 design.md。
- 父任务归档：`.trellis/tasks/archive/2026-07/07-17-ws-ticket-status-p2`
