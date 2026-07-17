# Implement — Voice finalize close code

## Checklist

1. [x] **Finalize 语义**：`_finalize_voice_session` 将 `!= DISCONNECTED` 改为 `== CONNECTED` 再 `close()`。
2. [x] **consume 竞态测试**：`test_consume_race_abandons_dashscope_session` 断言 `[4401]`；FakeWs close 后保持 `CONNECTING`。
3. [x] **ASR start 失败测试**：新增 `test_dashscope_start_fail_keeps_close_1011`，断言 `[1011]`。
4. [x] **门禁**：`test_device_app_voice_ws_ticket_burn.py` + `ruff check`  touched files。

## Validation commands

```powershell
.\.venv310\Scripts\python.exe -m pytest tests/test_device_app_voice_ws_ticket_burn.py -v -q --tb=short
.\.venv310\Scripts\python.exe -m ruff check routes/device_app_voice_ws.py tests/test_device_app_voice_ws_ticket_burn.py
.\.venv310\Scripts\python.exe scripts/check_code_size.py routes/device_app_voice_ws.py
```

不要求 fz `agent_gate`（纯语音 WS 路径，无 G-code/运动变更）。

## Review gates

- [x] pre-accept 4401/1011 不被 finalize 无码 close 覆盖
- [x] post-accept 正常路径仍可由 finalize 关闭连接
- [x] Ponytail：最小 diff（finalize 条件 + 测试）

## Rollback

还原 `routes/device_app_voice_ws.py` 与 `tests/test_device_app_voice_ws_ticket_burn.py` 即可。
