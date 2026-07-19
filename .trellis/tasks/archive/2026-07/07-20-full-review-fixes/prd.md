# PRD — 全量审查修复（2026-07-20）

## 背景

2026-07-20 全量项目审查（6 路并行逐文件通读 + 主线程复核）产出 3 Blocker + 一批 Warning。
本任务批量修复其中软件侧问题。固件（esp32S_XYZ）WDT 设计问题涉及 sdkconfig 决策与硬件验证，**不在本任务范围**，另行立项。

## 修复清单（验收标准 = 每项修复 + 对应测试通过）

### Blocker

- [x] B1 `chat-web/voice-call.html:266` — `ws.send(JSON.stringify({...}` 缺右括号，语音通话页全断。补 `))`，`node --check` 通过。
- [x] B2 `dlc_mcp/mcp_pipe.py:99-104` — WS 正常关闭时 `asyncio.gather` 永不返回，bridge 死锁不重连。改 `asyncio.wait(FIRST_COMPLETED)` + 取消其余任务，`finally` 终止子进程后重连循环可再入。
- [x] B3 部署工具链：`scripts/deploy_unified_common.py` `_DEPLOY_EXCLUDES` 加 `.venv`（或在 `_resolve_local_module` 跳过 `site-packages` 路径）；`requirements_dev.txt` 补 `ruff` 并安装。4 个红测试（test_deploy_unified*、test_ci_gates::test_ruff_gate_passes）转绿。

### Warning（物理安全优先）

- [x] W1 `device_gateway/task_creation_builders.py:123` — `validate_capability_params` 未传已解析的 profile，run_path 工作区校验被跳过。把 `resolved` 穿透进去。
- [x] W2 `dlc_core/path_validator.py` — Z 轴不校验。按 `bounds["z"]` 校验。
- [x] W3 `device_gateway/coordinator.py:132` — `merge_results` 不认 `dispatched`，批量调度恒报 success_count=0。
- [x] W4 `device_gateway/redis_store_queue.py:144` — `recovered_at` 永不清除且 `status=="processing"` 从未赋值，恢复后合法 ack 全被拒。再派发时清 `recovered_at`。
- [x] W5 `rate_limiter.py:82-99` — Redis 路径 `expire` 失败留下无 TTL 键永久卡死；INCR+EXPIRE 原子化（pipeline/Lua）。固定窗口语义差异记录到注释即可（不强制改滑动窗口）。
- [x] W6 `routes/device_app_stats.py:85-99` — `hour` 为 None/越界时跳过，避免 500。
- [x] W7 `device_logic/notifications.py` — `_build_payload` 移入 try 或用 `format_map` 容错缺 key；`_log_notification` 包 `asyncio.to_thread`；后台任务 done-callback 记录异常。
- [x] W8 `chat-web/chat-messages.js:72-78` — 图片 markdown 先于全局 `escapeHtml` 提取（同代码块处理方式），消除双重转义。
- [x] W9 chat-web 6 页面补 `frame-ancestors 'none'`（或 `_headers` 加 `X-Frame-Options: DENY`）。
- [x] W10 `dlc_core/device_status.py:8` — 分层倒置：`_build_device_status` 下沉，`routes` 与 `dlc_core` 均从下层导入。
- [x] W11 `device_gateway/registry.py:118`、`gallery_service.py:190` — 阻塞调用包 `asyncio.to_thread`。
- [x] W12 `routes/images.py:188` — 复用 `request_tracking.client_ip`，不再裸信 XFF。

### 不修（记录原因）

- 语音 ticket 双连竞态（R3）：代码已注释承认，30s TTL + 一次性 ticket，风险有限，改动涉及连接槽时序重构。
- `dlc_api/routes.py` 绕过 façade、403/200 不一致、GET 写库、声纹 409、transfer 守卫、audio_store startswith、dispatch 锁泄漏等 Suggestion 级：低风险，留待日常迭代。
- 固件 WDT（PANIC 开关、心跳间隔）：需硬件在环验证，单独立项。

## 硬门禁

- `ruff check` 全绿；`pytest tests/` 无新增失败（基线：4 失败须转绿，1852 通过不回退）。
- 单文件 ≤300 行、单函数 ≤50 行。
- 每项修复附回归测试（已有测试覆盖的除外）。
