# Implement — Review closure

## Checklist

1. [x] `device_voice/streaming_asr.py` — `validate_voice_stream_available()`
2. [x] `routes/device_app_voice_ws.py` — reorder validate/consume/accept/open；条件 finalize
3. [x] `dlc_mcp/server.py` — `_tool_result` `isError: False`
4. [x] `routes/device_app_status_ws.py` — `_resolve_task_terminal_event`
5. [x] 测试更新/新增（voice burn、MCP、status WS）
6. [x] 门禁与归档

## Validation

```powershell
.\.venv310\Scripts\python.exe -m pytest tests/test_device_app_voice_ws_ticket_burn.py tests/test_dlc_mcp_server.py tests/test_device_app_status.py tests/test_app_status_ws_ticket.py -q
.\.venv310\Scripts\python.exe -m ruff check device_voice/streaming_asr.py dlc_mcp/server.py routes/device_app_status_ws.py routes/device_app_voice_ws.py tests/test_device_app_voice_ws_ticket_burn.py tests/test_dlc_mcp_server.py tests/test_device_app_status.py
.\.venv310\Scripts\python.exe scripts/check_code_size.py routes/device_app_voice_ws.py routes/device_app_status_ws.py
```

## Rollback

还原上述 4 个源文件与 3 个测试文件即可。
