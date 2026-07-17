# Implement — 后端预发布 P1 加固

## Checklist（顺序）

1. **Settings / JWT typ (R1)**
   - 解析 `LIMA_JWT_REQUIRE_TYP` + 生产默认
   - `device_logic/auth.py` + `admin_auth.py` 拒绝无 typ
   - 测：`tests/test_device_logic_auth.py`（及 admin 对称）

2. **Rate limit 生产忽略 disable (R6)**
   - 统一 accessor / settings 行为
   - 测：生产 runtime 下 disable=1 仍限流（可挂现有 rate 测）

3. **SQLite WAL (R5)**
   - `config/sqlite_pool.py` 新建连接 PRAGMA
   - 测：连接后 `PRAGMA journal_mode` 为 wal

4. **Idempotency fail-closed (R4)**
   - `idempotency.py` 生产 raise/三态
   - `dlc_api/routes.py` → 503
   - 测：mock redis down + production

5. **Voice consume after start (R3)**
   - 重排 `_run_voice_stream_ws`
   - 测：扩展 `test_device_app_voice_ws_ticket_burn.py`（start 失败不烧；成功烧）
   - 更新 `docs-site/api/voice.md`

6. **Status 未知不推送 (R8)**
   - `_resolve_task_terminal_event` → Optional
   - 测：未知状态无 `task_completed`

7. **MCP 空 token (R7)**
   - `main()` 远程 URL 校验
   - 测：subprocess 或直接调校验函数

8. **门禁**
   - 相关 pytest 全绿
   - `ruff check` 改动路径
   - 代码尺寸（单文件 ≤300 / 函数 ≤50）

## Validation commands

```powershell
cd D:\QWEN3.0
.\.venv310\Scripts\python.exe -m pytest tests/test_device_logic_auth.py tests/test_device_app_voice_ws_ticket_burn.py tests/test_device_app_voice_ws_device_id.py tests/test_dlc_rate_limit_idempotency.py tests/test_p2_idempotency_rollback.py tests/test_device_app_status.py tests/test_dlc_mcp_server.py -q
ruff check device_logic/auth.py device_logic/admin_auth.py routes/device_app_voice_ws.py routes/device_app_status_ws.py dlc_api/idempotency.py dlc_api/routes.py config/sqlite_pool.py config/settings_core.py dlc_mcp/server.py
python scripts/check_code_size.py  # 若项目惯例入口不同则用现有门禁
```

（实现时按实际新增测试文件名微调。）

## Risky files / rollback

| 文件 | 风险 | 回滚点 |
|------|------|--------|
| `device_app_voice_ws.py` | 烧票顺序回归 | 恢复 consume-before-accept |
| `idempotency.py` | 生产 Redis 抖 → 503 增多 | 临时非生产或 flag（若加） |
| `auth.py` | 旧 token 全失效 | `LIMA_JWT_REQUIRE_TYP=0` |

## Before `task.py start`

- [x] prd / design / implement 齐
- [ ] 用户确认规划
- [ ] `implement.jsonl` / `check.jsonl` 已填真实 spec（非 `_example`）

## Notes

- 不跑 fz `agent_gate`（无 G-code/运动路径改动）。
- 不 `git add .`；用户未要求不 commit。
