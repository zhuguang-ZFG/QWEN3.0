# WS ticket 烧票 + status 终态事件（review P2）

## Goal

修复第二轮 code review 中的 P2：**voice/status WebSocket 在失败路径上不应消耗一次性 ticket**。不含真机 HIL；不含 status 终态 completed vs failed（R3 另开任务）。

## Background（已核实）

- Voice：`routes/device_app_voice_ws.py` 在 `_authorize_voice_ws` 中 `consume_if` 消耗 ticket，随后才检查并发槽与 ASR；槽满（4429）或 `AsrNotConfiguredError`（1013）会烧票。
- Status：`routes/device_app_status_ws.py` 在 `_authorize_ws` 中 `consume` 消耗 ticket，随后 `try_acquire` 失败同样烧票。
- 产品范围决定（2026-07-17）：**仅 R1+R2**；R3 终态事件 Out of Scope。

## Requirements

### R1 — Voice WS 失败不烧票

- 下列情况**不得**消耗 ticket：
  - 并发槽已满（关闭码 4429）
  - ASR 未配置 / 启动失败导致关连接（如 1013）
- 无效/过期 ticket、非活跃账号：**不消耗**（与现有 `consume_if` 对无效账号行为一致）。
- 成功 `accept` 并进入收流后，ticket **必须已消耗**（防重放）。

### R2 — Status WS 失败不烧票

- 并发槽已满（4429）不得消耗 ticket。
- 设备访问拒绝 / 鉴权失败不得消耗仍有效的 ticket。
- 成功进入 status 会话后 ticket 必须已消耗。

## Out of Scope

- R3：status WS `task_completed` vs `task_failed`（另开任务）
- 真机 HIL / 纸路 / BT
- Ticket 存储迁 Redis、多 worker 共享
- `dlc_core/dispatch.py` 锁字典淘汰

## Acceptance Criteria

- [x] Voice：槽满路径自动化测试证明 ticket 未被消耗（可再次用于成功路径或仍可 peek）
- [x] Voice：ASR 不可用路径自动化测试证明 ticket 未被消耗
- [x] Status：槽满路径自动化测试证明 ticket 未被消耗
- [x] Voice/Status：成功进入会话后，同一 ticket 再次使用失败（已消耗）
- [x] 现有 voice/status WS 回归测试全绿；无新增静默 `except: pass`
- [x] `ruff check` + 相关 pytest 通过；改动触及文件仍 ≤300 行 / 函数 ≤50 行

## Notes

- Complex task：`design.md` + `implement.md` 齐全后再 `task.py start`。
- 推荐：**延迟到即将 accept 再 consume**（peek → 槽/ASR → consume → accept）。
