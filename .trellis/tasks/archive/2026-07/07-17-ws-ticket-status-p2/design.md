# Design — WS ticket 延迟消耗

## Boundaries

| In | Out |
|----|-----|
| `routes/device_app_voice_ws.py` 鉴权/进会话顺序 | Status 终态事件（R3） |
| `routes/device_app_status_ws.py` 鉴权/进会话顺序 | Ticket 迁 Redis |
| 必要时微调 `voice_app_ws_ticket` / `app_status_ws_ticket` API（若需 `peek` 对称） | 部署/nginx 变更 |
| 对应 pytest | 真机 E2E |

## Approach

**延迟 consume**：鉴权阶段只 **peek**（校验账号/设备绑定），通过并发槽与 ASR（voice）检查后，在 **`websocket.accept()` 之前** 原子 consume；任一步失败则 close，ticket 仍有效。

### Voice 目标顺序

1. `peek(ticket)` → account_id；无/过期 → close 4401（不 consume）
2. `load_active_account` + 有效 → 继续；无效 → 4401（不 consume）
3. rate limit / `try_acquire` 失败 → 4429（不 consume）
4. `open_voice_stream_session`；`AsrNotConfiguredError` → 1013（不 consume）
5. `consume_if(ticket, pred)`；失败 → 4401（竞态下另一连接已用）
6. `accept()` → 收流；`finally` `release` 槽

### Status 目标顺序

1. ticket 路径：`peek` 校验 device_id + account + `require_device_access`（不 consume）
2. query-token 路径：保持现有（无 ticket，不涉及烧票）
3. `try_acquire` 失败 → 4429（不 consume）
4. `consume(ticket)`；失败 → 1008
5. `accept()` → 轮询；`finally` `release`

## Contracts

- **关闭码语义不变**：4401/4429/1013/1008 含义不变；仅改变「是否烧票」。
- **成功路径**：accept 后同一 ticket 再次连接必须失败（已消耗）。
- **API**：
  - Voice 已有 `peek` + `consume_if` — 优先复用，鉴权阶段改用 peek。
  - Status 仅有 `consume` — 新增 `peek(ticket) -> (device_id, account_id) | None`（与 voice 对称），或拆出「校验但不 pop」；禁止在失败路径 `consume` 后再「写回」（不可靠）。

## Compatibility

- 小程序：无协议字段变更；仅失败后可重用未过期 ticket（30s TTL 内），体验变好。
- 多 worker：仍为进程内 ticket（本任务不改）；与现状一致。

## Trade-offs

| 方案 | 取舍 |
|------|------|
| **延迟 consume（选）** | 实现清晰；accept 前短窗口内两连接可能竞态双 peek，靠 consume 原子性只放行一个 |
| 失败后 re-issue 新 ticket | 需服务端写回或客户端再调 ticket API；不如不烧 |
| accept 后再 consume | 已建立 WS 再鉴权失败体验差；且中间帧可能到达 |

## Rollout / Rollback

- 纯服务端行为修复；部署 `routes/device_app_voice_ws.py`、`routes/device_app_status_ws.py`、可选 ticket 模块。
- 回滚：还原上述文件即可；无数据迁移。

## Test shape

- 单元：ticket peek/consume 行为（status 新增 peek）。
- 集成（TestClient WS）：槽满不烧；ASR mock 不可用不烧；成功路径烧票。
- 复用/扩展：`tests/test_device_app_voice_ws.py`、`tests/test_device_app_status.py`、`tests/test_voice_app_ws_ticket.py`；必要时 `test_app_status_ws_ticket.py`。
