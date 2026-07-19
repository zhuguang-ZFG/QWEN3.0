# Journal - zhugu (Part 1)

> AI development session journal
> Started: 2026-07-14

---


## Session 1: P2 代码审查 + A2A 舰队复核修复 + 60+ 存量落盘

**Date**: 2026-07-16
**Task**: P2 代码审查 + A2A 舰队复核修复 + 60+ 存量落盘
**Package**: root
**Branch**: `fix/code-review-p2-hardening`

### Summary

A2A 8-agent 对 working-tree diff 复核出 8 findings（7 CONFIRMED + 1 REFUTED）。修复 7 处：idempotency L1 无界泄漏(惰性清扫+4096 上限，保留 recovery barrier)、status WS 槽泄漏(accept 移入 try/finally)、voice WS 三处 wait_for 超时未捕获、admin 订阅者被静默过滤(补 role)、status WS 轮询阻塞(to_thread)、notifications N+1(to_thread)、dlc_mcp 静默吞异常。测试驱动修正了 idempotency 方案(初选释放 L1 破坏 recovery barrier，改惰性清扫)。随后落盘 60+ 会话前存量改动(队列抽取/认证 fail-closed/部署门禁/voice 链/infra)，10 commit 分主题提交，全量 1780 passed。submodule manifest 文案优化一并 bump pin。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `d873b917` | (see git log) |
| `4f7e2aa0` | (see git log) |
| `2f1ee951` | (see git log) |
| `f7089f1a` | (see git log) |
| `1ad558d6` | (see git log) |
| `bfc44c46` | (see git log) |
| `e8f1588d` | (see git log) |
| `2e7745f1` | (see git log) |
| `3f4f06b9` | (see git log) |
| `248ba3cc` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

---


## Session 2: 00-bootstrap-guidelines — 填充 esp32S_XYZ 固件后端规范

**Date**: 2026-07-16
**Task**: 00-bootstrap-guidelines (P1 Trellis 引导任务)
**Package**: esp32S_XYZ
**Branch**: `main`

### Summary

完成 Trellis bootstrap 引导任务，为 esp32S_XYZ 双 MCU 固件子模块填充实质开发规范（此前 `backend/` 为空、包级 index 仅写「沿用上游、不加规则」）。后台 Explore agent 深度调查 7 维度（U1 Grbl/U8 xiaozhi 固件、4 通信边界 schema、测试体系、上游约定、docs、工具链），据此撰写 4 份 backend 规范。核心原则遵循 PRD「document reality, not ideals」——4 轮批量核实所有承重事实（版本号/文件路径/GPIO 常量/schema 枚举/章节号），逐一对真实代码库比对。

### Main Changes

- `backend/index.md`：双 MCU 架构、技术栈版本表、改动边界铁律（U1 只改机型头 `dlc_motor_control_p1.h` / U8 只改板目录 `dlc-motor-control-p1-ai/`，上游代码不改）、make 命令速查
- `backend/u1-grbl.md`：Grbl_Esp32 clang-format（ColumnLimit 140/Indent 4）、机型文件结构、运动能力现状表、strapping pin {0,3,45,46} 风险、真实代码示例、FluidNC 迁移方向
- `backend/u8-xiaozhi.md`：xiaozhi camelCase 方法名约定（与 U1 snake_case 不同）、cJSON/NVS/HTTPS 强制/OTA A/B/超时禁 0 红线、未落地项（抬笔/独立急停/龙门矫正）
- `backend/edge-d-contract.md`：Edge-D `@{json}\n` 帧、11 cmd/7 state 枚举、alarm_code(E001-E009) vs error_code(恒 null) 区分、字段演进铁律（先改 schema→fake→固件→test_edge_d_firmware_static.py）、工具链
- 修订 `spec/esp32S_XYZ/index.md`：去掉过时的「xiaozhi-esp32-server 上游/主仓库不加规则」，指向 backend/
- 勾选 PRD 两项完成

### 核验修正（document reality 的价值）

- agent 转述的 `STEPPERS_ALWAYS_ENABLED` 不存在 → 真实是 `DEFAULT_STEPPER_IDLE_LOCK_TIME=25`（ms，`Stepper.cpp` `*1000` 转 μs，停止后释放使能让 Z 弹簧回 pen-up）
- agent 转述的 `MotorClass.h` 不存在 → 真实为基类 `Motor.h` + 工厂 `Motors.cpp`
- agent 混淆 `alarm_code`/`error_code` → 契约文档精确区分
- 宏形态 `GPIO_NUM_46`（非 `GPIO46_`）
- 8 个架构文档章节号引用（§5.4/§10bis.7/9/10/12/§14/§15.4/§16.5）逐一对 111KB 主纲核对，全部语义匹配

### Git Commits

| Hash | Message |
|------|---------|
| `8589c6e6` | docs(esp32S_XYZ): 填充固件后端开发规范 |
| `8715d89c` | chore(task): archive 00-bootstrap-guidelines |

### Testing

- [OK] 纯 docs 改动，无代码变更；事实核验通过 4 轮批量比对 + 章节号逐条核对

### Status

[OK] **Completed** — bootstrap 任务归档至 `archive/2026-07/`

### Next Steps

- 后续新开发者将获得 `00-join-<slug>` onboarding 任务（非 bootstrap）
- 固件规范里标注的未落地项（抬笔保护/独立急停/龙门矫正）为独立实施任务

---


## Session 3: A2A 舰队 code-review DEBUG — 两批复核（3 真 bug 修复 + 16 条证伪/降级）

**Date**: 2026-07-16
**Task**: code review DEBUG（P2 加固 31 文件）
**Package**: root
**Branch**: `main`

### Summary

对 P2 加固涉及的 31 个 Python 文件做两批 A2A 舰队 code review（Reasonix 4944 / AtomCode 4940 / Kimi 4945 三节点并行，我逐条亲验把关）。第一批深审 6 个最高风险文件，报 9 条全部真实（严重度夸大），修 3 条真 bug；第二批复核其余 11 个运行时关键文件，报 16 条经亲验全部证伪或降级为设计权衡，真 bug 0 条。code review 任务收敛。

### 第一批：真 bug 修复（commit `f390cac6`）

| 位置 | 问题 | 修复 |
|------|------|------|
| `dlc_mcp/server.py:259` | 异常分支硬编码 `_tool_error(None,...)` 丢失 req id，配合 L260 过滤器致内部错误响应被静默丢弃 | 回填 `req.get("id") if isinstance(req,dict) else None` |
| `dlc_mcp/server.py:260` | 输出过滤器 `id is not None` 吞掉合法的 id:null 错误响应（-32600 Invalid Request），违反 JSON-RPC | 加 `or resp.get("error") is not None`；notification `{}` 仍正确跳过 |
| `routes/device_app_voice_ws.py:190` | DashScope 分支 `wait_for(session.close())` 无 try/except，超时异常穿透跳过 ws.close 致连接槽泄漏 | 包 try/except Exception + warning |
| `device_voice/streaming_asr.py:129` | 丢弃 `run_coroutine_threadsafe` 的 future，_handler 异常静默 | 保存 future + done_callback 记 debug |

连带：`_start_sync` 因 +2 行 done_callback 达 51 行超 50 门禁 → 抽 `_build_collector` 模块级工厂重构，降到 17 行。

新增 4 个回归测试锁 bug（3 dlc_mcp + 1 voice finalize）。ruff + 尺寸门禁 + 全量 1787 passed / 0 failed（git stash 确定性验证测试零丢失）。

### 第二批：16 条全证伪/降级（无需改动）

三节点复核 11 文件（device_gateway 队列/存储、dlc_core/dispatch、device_logic 核心、dlc_api），共报 3 P0 + 6 P1 + 若干 P2，逐条亲验：

- **Kimi `chat_store.get_messages` 越权读 P0** → 证伪：全仓库零调用方（死代码），无攻击面
- **Kimi `list_audio_history` 越权读 P0** → 证伪：唯一调用方 `device_app_chat.py:43` 已 `require_device_access`
- **Kimi `persist_audio_clip` 越权写 P1** → 证伪：调用方 L81 已 `require_device_control`
- **AtomCode `routes.py:198` CancelledError 泄漏幂等键 P2** → 证伪：CancelledError 保留幂等键是**故意正确**的语义（不确定是否送达设备时必须保守，释放键才会导致重复下发）
- **Reasonix 队列 3×P1（幽灵任务/requeue 丢失/ack TOCTOU）** → 降级：均为 at-least-once 队列已知设计权衡，有 `recover_stale_processing` + L145 反双花守卫兜底
- 其余（dispatch 锁无界 / notifications N+1 / hgetall 无分页）→ 上轮已知或单-worker 下非问题

### 关键经验（写入以避免重复 review）

- **A2A 高危报告必须亲验，尤其 P0**：本 session 两批对比鲜明——第一批（自包含的 correctness bug）9 条全真；第二批（强依赖跨文件设计意图的授权/幂等/队列原子性）3 P0+1 P2 全假。根因：A2A agent 只拿孤立文件，缺调用方视野 + 架构上下文，把「API 层已鉴权的 storage 函数」和「正确的保守幂等设计」误报成高危。
- **A2A transcript 泄漏**：Kimi 节点返回混入大量思考过程（它自己在 transcript 里已纠结 storage vs API 层鉴权，仍报 P0），只取 VERDICT 行、丢弃噪音。
- **11 文件复核结论 = 无需改动**，下次勿重复 review：`redis_store_queue.py` `redis_store.py` `tasks.py` `dispatch.py` `gateway.py` `routes.py` `deps.py` `chat_store.py` `notifications.py` `audio_clips.py`。

### Git Commits

| Hash | Message |
|------|---------|
| `f390cac6` | fix: 修复 MCP 静默吞响应 + voice WS 异常穿透（A2A 舰队修复，逐行审核） |

### Testing

- [OK] 全量 1787 passed / 3 skipped / 0 failed（`.venv310` Python 3.10）
- [OK] ruff check + format + 代码尺寸门禁全绿
- [OK] git stash 确定性验证：基线 1783 collected → 现 1787（净增 4 回归测试，零丢失）

### Status

[OK] **Completed** — code review 收敛，真 bug 全修，main 已 push origin

### Next Steps

- 第二批 11 文件确认无需改动，不再重复 review
- 竞态类防御性改进（idempotency L1 误删窗口 / to_thread 不可取消 / 无锁 TOCTOU）如需处理应单独开任务，避免为极低概率问题引入新复杂度


## Session 4: Ponytail 硬门禁债务清理（4 长函数≤50）

**Date**: 2026-07-17
**Task**: Ponytail 硬门禁债务清理（4 长函数≤50）
**Package**: root
**Branch**: `main`

### Summary

AST 巡检 213 文件：0 文件>300、ruff clean、6 处静默异常经复核全为窄类型误报（不动）。4 个轻微超长函数（51-63 行）抽模块内私有 helper 降级≤50。舰队编排：Reasonix 首轮抽 helper 跑通，但 Atom 审核 + Reasonix 修复派发 4/5 卡在 A2A 桥接 240s 天花板取消，转 Claude 直改+复核。复核独立抓到并修 3 处：handwriting font 键条件、render_asset status 复用、deploy _connect_ssh 与 restart 逐字重复改为复用（文件 317→296 过≤300，test patch 目标随之改 restart 命名空间）。验收 check_code_size PASS / ruff+format clean / pyright 0 / 37 tests passed。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `d0d15df1` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

## Session 5: WS ticket 延迟 consume（review P2）

**Date**: 2026-07-17
**Task**: WS ticket 烧票 + status 终态事件（仅 R1+R2）
**Package**: root
**Branch**: main

### Summary

第二轮 code review 发现 Voice/Status WS 在槽满/ASR 不可用时先 consume 烧票。实现延迟 consume：peek → 槽/(ASR) → consume → accept。R3 终态事件 Out of Scope。

### Main Changes

-
outes/device_app_voice_ws.py / device_app_status_ws.py
- pp_status_ws_ticket.peek
- 烧票回归测试（拆 	est_device_app_voice_ws_ticket_burn.py 过 ≤300）
- docs-site/api/voice.md、.trellis/spec/root/error-handling.md

### Git Commits

| Hash | Message |
|------|---------|
| 8d11f206 | fix: WS ticket 延迟 consume，失败路径不烧票 |

### Testing

- [OK] 相关 pytest 34+ passed；ruff + check_code_size PASS；trellis-check PASS

### Status

[OK] **Completed** — 已 archive

### Next Steps

- R3 status task_completed vs failed 另开任务（若需要）

## Session 6: Voice finalize close code（review P2）

**Date**: 2026-07-17
**Task**: Voice WS finalize close code（review P2）
**Package**: root
**Branch**: main

### Summary

深度 review 遗留 P2：pre-accept 失败已 `close(4401/1011)` 后，`_finalize_voice_session` 无码 `close()` 可能覆盖 intentional code。改为仅 `CONNECTED` 时补 close；补 close-code 回归断言。

### Main Changes

- `routes/device_app_voice_ws.py` — finalize 条件 `!= DISCONNECTED` → `== CONNECTED`
- `tests/test_device_app_voice_ws_ticket_burn.py` — 断言 `[4401]` / `[1011]`；FakeWs CONNECTING 护栏

### Git Commits

| Hash | Message |
|------|---------|
| 45b2e909 | fix: Voice finalize 不覆盖 pre-accept close code |

### Testing

- [OK] `test_device_app_voice_ws_ticket_burn.py` 5 passed
- [OK] ruff + check_code_size PASS

### Status

[OK] **Completed** — 已 archive `.trellis/tasks/archive/2026-07/07-17-voice-close-code-p2`

### Next Steps

- Voice ASR pre-accept 创建时机（P2 设计项，另开任务）
- MCP `isError: false` 需 xiaozhi.me E2E 验证后再改

## Session 7: Status WS finalize close + consume_if（review P2/P3）

**Date**: 2026-07-17
**Task**: Status WS finalize close + consume_if
**Package**: root
**Branch**: main

### Summary

深度 review 落地：Status WS `_finalize_status_ws` 仅 CONNECTED 补 close；`app_status_ws_ticket.consume_if` 对称 Voice；consume 失败 close code 回归断言。

### Main Changes

- `app_status_ws_ticket.py` — `consume_if`
- `routes/device_app_status_ws.py` — `_finalize_status_ws`、consume 路径
- `tests/test_app_status_ws_ticket.py` — consume_if + close 1008 护栏

### Git Commits

| Hash | Message |
|------|---------|
| 8f184ad6 | fix: Status WS finalize close + consume_if |

### Testing

- [OK] status/ticket 15 passed；ruff + check_code_size PASS

### Status

[OK] **Completed** — 已 archive `.trellis/tasks/archive/2026-07/07-17-status-ws-close-consume`

## Session 8: Review closure（Voice ASR / MCP isError / R3 terminal）

**Date**: 2026-07-17
**Task**: Review closure — voice ASR after accept, MCP isError, task terminal events
**Package**: root
**Branch**: main

### Summary

关闭 review 三项：Voice WS 在 validate 通过、consume、accept 后才打开 ASR 会话；MCP `tools/call` 成功响应含 `isError: false`；Status WS 按 `task_snapshot` / `v2_task` 区分 `task_completed` 与 `task_failed`。

### Main Changes

- `device_voice/streaming_asr.py` — `validate_voice_stream_available()`
- `routes/device_app_voice_ws.py` — 重排 validate→consume→accept→open；条件 finalize
- `dlc_mcp/server.py` — `_tool_result` 增加 `isError: False`
- `routes/device_app_status_ws.py` — `_resolve_task_terminal_event`
- 测试：voice burn、MCP isError、status WS 终态过渡

### Git Commits

| Hash | Message |
|------|---------|
| `31a650dd` | fix: review closure — voice ASR after accept, MCP isError, task terminal |

### Testing

- [OK] 指定 pytest 35 passed
- [OK] ruff + check_code_size PASS

### Status

[OK] **Completed** — 已 archive `.trellis/tasks/archive/2026-07/07-17-review-closure`

### Next Steps

- xiaozhi MCP E2E 验证 `isError` 字段（可选）


## Session: SoftAP device_secret portal + ensure gate

**Date**: 2026-07-17
**Task**: 07-17-softap-device-secret-align
**Package**: esp32S_XYZ

### Summary

SoftAP Connect form optional device_secret/server_host; patch CC+HTML; ensure dual markers with surgical fallback. Submodule e38dd59; Trellis u8 SoftAP spec note.

### Status

[OK] Completed — archive/2026-07/07-17-softap-device-secret-align


## Session: 后端预发布 P1 加固

**Date**: 2026-07-17
**Task**: 07-17-backend-prelaunch-p1
**Package**: root
**Branch**: main

### Summary

落地预发布审查 P1 子集 S：JWT typ 生产门禁、Voice start 后烧票、幂等生产 503、SQLite WAL、生产忽略 RATE_LIMIT_DISABLE、MCP 远程空 token 启动失败、Status 未知不推 terminal。trellis-check PASS。

### Status

[OK] Completed — pending archive/deploy


## Session 5: 全量审查修复收尾：子模块指针提升与任务归档

**Date**: 2026-07-20
**Task**: 全量审查修复收尾：子模块指针提升与任务归档
**Package**: root
**Branch**: `main`

### Summary

07-20-full-review-fixes 收尾：3 Blocker + 12 Warning 修复已随 8bbd5c3d 落地(ruff 全绿)；提交 esp32S_XYZ 指针提升至 500e9c6(WDT 注册修复 H2)；任务归档至 archive/2026-07。固件 WDT 设计问题(PANIC 开关、心跳间隔)仍需单独立项做硬件在环验证。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `8bbd5c3d` | (see git log) |
| `008793be` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
