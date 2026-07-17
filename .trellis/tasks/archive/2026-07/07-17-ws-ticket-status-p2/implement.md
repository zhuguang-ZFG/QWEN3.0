# Implement — WS ticket 延迟消耗

## Checklist

1. [x] **Status ticket API**：为 `app_status_ws_ticket` 增加 `peek`（不 pop）；单测覆盖 peek/consume/过期。
2. [x] **Voice WS 重排**：`_authorize_voice_ws` 改为 peek-only；槽检查与 ASR open 成功后再 `consume_if`，然后 `accept`。
3. [x] **Status WS 重排**：`_authorize_ws` ticket 路径改为 peek；`try_acquire` 成功后再 `consume`，然后 `accept`。
4. [x] **回归测试**：
   - Voice：槽满不烧；ASR 不可用不烧；成功后二次 ticket 失败。
   - Status：槽满不烧；成功后二次 ticket 失败。
5. [x] **门禁**：相关 pytest + `ruff check`；确认改动文件 ≤300 行 / 函数 ≤50 行。
6. [x] **文档（可选最小）**：`docs-site/api/voice.md` 补「进入会话前失败不消耗」。

## Validation commands

```powershell
.\.venv310\Scripts\python.exe -m pytest tests/test_voice_app_ws_ticket.py tests/test_app_status_ws_ticket.py tests/test_device_app_voice_ws.py tests/test_device_app_status.py tests/test_voice_ws_connections.py tests/test_app_status_ws_connections.py -q --tb=short
.\.venv310\Scripts\python.exe -m ruff check routes/device_app_voice_ws.py routes/device_app_status_ws.py voice_app_ws_ticket.py app_status_ws_ticket.py
.\.venv310\Scripts\python.exe scripts/check_code_size.py routes/device_app_voice_ws.py routes/device_app_status_ws.py app_status_ws_ticket.py
```

不要求 fz `agent_gate`（无 G-code/运动路径变更）。

## Review gates

- [x] 失败路径（4429 / 1013）后同一 ticket 仍可用于下一次成功连接（TTL 内）
- [x] 成功 accept 后 ticket 不可重放
- [x] 无静默 `except: pass`；关闭码语义未改
- [x] Ponytail：最小 diff，不顺手做 R3

## Rollback

还原本任务触及的 ticket + 两个 WS route 文件；无需 DB/Redis 回滚。

## Notes for implementer

- Active task: `.trellis/tasks/07-17-ws-ticket-status-p2`
- 优先读：`prd.md` → `design.md` → 本文件
- ASR 不可用：mock `open_voice_stream_session` / `AsrNotConfiguredError`，勿打真 DashScope
