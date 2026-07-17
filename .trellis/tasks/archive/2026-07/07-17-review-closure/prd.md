# Review closure — Voice ASR / MCP isError / task terminal (R3)

## Goal

关闭深度 code review 遗留的三项：Voice WS ASR 会话在 accept 后打开；MCP tools/call 成功响应含 `isError: false`；Status WS 按任务终态区分 `task_completed` vs `task_failed`。

## Requirements

### R1 — Voice ASR after accept

- 新增 `validate_voice_stream_available()`，从 `open_voice_stream_session` 提取配置校验，不创建 DashScope 会话。
- `_run_voice_stream_ws` 顺序：validate → consume → accept → open session → start/receive。
- 未配置时 1013 在 consume 之前（票不烧）；finalize 仅当 `session is not None`。
- 移除 `_create_asr_session`。

### R2 — MCP isError

- `dlc_mcp/server.py` `_tool_result` 在 result 对象增加 `"isError": False`（xiaozhi MCP 协议）。

### R3 — task_completed vs task_failed

- `_resolve_task_terminal_event(task_id)`：`task_snapshot` phase（done/completed → completed；failed/cancelled/rejected → failed）；回退 `v2_task.status`；未知默认 `task_completed`。
- Status WS `activeTaskId` 清空时发送解析后的终态事件。

## Acceptance Criteria

- [x] `test_device_app_voice_ws_ticket_burn.py`：consume 竞态在 ASR open 前失败，`session` 未创建，`ws_codes == [4401]`
- [x] `test_dlc_mcp_server.py`：tools/call 成功断言 `isError is False`
- [x] `test_device_app_status.py`：`task_completed` / `task_failed` 过渡事件
- [x] 指定 pytest 35 passed；ruff + check_code_size PASS

## Out of Scope

- G-code / fz agent_gate（无运动路径变更）
- 真机 HIL / xiaozhi E2E
