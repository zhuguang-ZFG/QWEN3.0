# Implement — Status WS close + consume_if

## Checklist

1. [x] `app_status_ws_ticket.consume_if`
2. [x] `_consume_status_ticket_if_present` 改用 consume_if
3. [x] 提取/修复 `_finalize_status_ws`（仅 CONNECTED close）
4. [x] 单测 + close code 回归
5. [x] pytest + ruff

## Validation

```powershell
.\.venv310\Scripts\python.exe -m pytest tests/test_app_status_ws_ticket.py tests/test_device_app_status.py -q --tb=short
.\.venv310\Scripts\python.exe -m ruff check app_status_ws_ticket.py routes/device_app_status_ws.py tests/test_app_status_ws_ticket.py
```
