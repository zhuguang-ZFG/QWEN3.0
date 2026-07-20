# 全项目深度审查报告 — 2026-07-20（第三轮 / 复审）

> 范围：round2 已合入后的 **device_gateway + routes/voice/mcp + 残余物理安全**。
> 方法：主线程定点复现 + 两路只读 explore（非慢实现子代理）。
> round2 Blocker（GW-B1/B2、CORE-O4 dlc_core、FW-F1/F3 代码、FE-1 等）**已修**，本轮不重复开单，除非证明修复不完整。

**主线程已复现确认（证据级）**

| ID | 结果 |
|----|------|
| GW-R3-1 NaN feed | `validate_run_path_params(..., feed=nan)` → `err=None`, feed 仍为 NaN |
| GW-R3-3 profile workspace NaN | `profile_limit_error` 对 `workspace.x=NaN` + 点 x=999 → `None`（放行） |
| GW-R3-5 无 profile ±500 | `run_path` 点 x=400 → 接受 |
| GW-R3-7 multipass 后越界 | normalize 后 `apply_multi_pass(3,5)` max_x 可 >100 |
| RT-R3-1 模板 execute | 源码仍是 **先 dispatch 后 insert**（L192–193） |
| GW-WF 隐式 L 坐标 | `M0 0 L 10 0 20 10 30 0` 仅 2 点（应 4 点） |

---

## 🔴 Blocker（发布 / 物理安全前必修）

### GW-R3-1 — `run_path` 接受 NaN feed

- **位置**：`device_gateway/path_validator.py:82-88`
- **证据**：点坐标有 `math.isfinite`；feed 仅 `float()` + 比较。IEEE NaN 比较全 False → 原样下发。
- **影响**：G-code/固件 feed 未定义，运动行为不可控。
- **修法**：`not math.isfinite(feed) → E_BAD_PARAMS`（与 `_clamp_feed_value` / `safety.py` 对齐）。

### GW-R3-3 — 设备 profile 工作区 NaN 仍 fail-open（CORE-O4 未覆盖 gateway 路径）

- **位置**：`device_intelligence/safety.py:42-51`、`device_intelligence/schemas.py` workspace 归一化
- **证据**：`workspace_mm.x = NaN` 时 `x > NaN` 恒 False，点永不 “outside”。
- **影响**：影子/配置注入 NaN 工作区 → 小行程机器越界运动。
- **修法**：profile 构造与 `profile_limit_error` 均要求 `isfinite(v) and v > 0`。

### GW-R3-5 — gateway `run_path` 无 profile，仅 ±500mm 兜底

- **位置**：`device_gateway/path_validator.py:19-20`；`device_logic/gateway.py` 校验不传 profile
- **证据**：`[{x:400,y:0,z:0}]` + feed=500 → 通过；产品机 60–100mm。
- **影响**：与 pre-GW-B1 同类物理越界（API/网关直入队路径）。
- **修法**：入队前 resolve profile（或保守 60mm）；优先 `[0, workspace]`；越界 hard-fail。

### GW-R3-2 — 无 `dispatch_gen` 的 ack 在 re-dispatch 后可摘掉当前 processing

- **位置**：`redis_store_queue.py:167-201`；`task_events.py:133-137`
- **证据**：recover 抬 gen 并设 `recovered_at` → re-pop **清掉** `recovered_at` → 设备/通道若不回显 gen，则 `dispatch_gen=None` 走 LREM 成功。
- **影响**：陈旧 ack 可抹掉新派发记账 → 双花/丢任务/假 acked。
- **修法**：processing 条目要求 gen；gen-less 在 `dispatch_gen>0` 时拒绝；测试勿固化漏洞。

### GW-R3-4 — SEC-06 pop 只验 capability，不重验 path/feed

- **位置**：`redis_store_helpers.py` `validate_task_schema`；`redis_store_queue._gate_popped_tasks`
- **证据**：恶意/旁路 `RPUSH` 带越界 path 可通过门禁。
- **影响**：队列是信任边界；HTTP 校验可被绕过。
- **修法**：pop 时跑 `validate_capability_params`（+ profile），失败 mark failed。

### RT-R3-1 — 模板 execute 先 dispatch 后 insert

- **位置**：`routes/device_app_task_templates.py:192-193`
- **证据**：与 `device_app_task_create.py` insert-first 对冲；dispatch 成功 + insert 失败 = 幽灵入队无审计行。
- **修法**：insert pending → dispatch → 更新状态；失败 `mark_task_failed`。

---

## 🟠 Warning（尽快）

| ID | 摘要 | 位置 |
|----|------|------|
| ~~**GW-R3-6**~~ | **已修** fail-closed：预检异常返回错误串（对齐 `device_draw_handler`） | `handwriting_path.py:108-123` |
| ~~**GW-R3-7**~~ | ~~multi_pass **在** normalize 之后 → 可再次越界~~（**已修**，见下表） | `path_pipeline.py` render_* |
| ~~**GW-R3-8**~~ | **已修**（Option B）：`rejected` 解析不得被 LLM 改写成运动能力（write_text/draw/run_path/move_*），仅允许改写成控制类（stop/pause/home/...），恢复 GW-WH 不变量；默认仍门控于 `LIMA_DEVICE_LLM_PLANNER` | `intent.py` / `intent_llm_planner.py` |
| **GW-R3-9** | `queued_no_delivery` 仍占 busy 至 1h | `tasks.py` / `QUEUED_MAX_AGE_SEC` |
| ~~**GW-R3-10**~~ | **已修**（描述修正：非崩溃，NaN/Inf feed 静默钳到 MAX_FEED 2000 > 1200 安全上限）→ `task_draw_params._clamp_feed` 加 `math.isfinite` 回落 default，对齐已修的 handwriting 同名函数 | `task_draw_params.py` |
| **GW-R3-11** | feed 上限 2000 vs safety 1200 分裂 | path_validator vs safety |
| ~~**GW-R3-12**~~ | **已接通**（方向 A）：move_abs/move_rel 全链路打通（allowlist + 校验 + 投影 + 路由），加服务端工作区/±1mm 校验，语音模糊移动放行 | intent + path_validator + task_creation |
| **GW-WF** | SVG 隐式坐标序列丢失；相对 m 后隐式 l 不完整 | `svg_parser._handle_ml` |
| **RT-R3-2** | batch-draw 限流 1 次 / N 设备，无 device_ids 上限 | `device_app_tasks.py` |
| **RT-R3-3** | app `/tasks/preview` 无限流（可触发重路径生成） | `device_app_task_extras.py` |
| **RT-R3-4** | `dlc_image_task_per_min` 配置零引用 | settings vs tasks |
| **RT-R3-5** | pending 队列无深度上限 | enqueue_pending_task |
| **VO-R3-1** | 语音 ticket 在 ASR start 后才 consume → 双开会话窗 | `device_app_voice_ws.py` |
| **CORE-R3-1** | 幂等 claim 同步 Redis 卡事件循环 | `dlc_api/idempotency.py` |
| **CORE-R3-2** | dlc token Depends 同步 SQLite | `dlc_api/deps.py` |
| **CORE-R3-3** | 幂等 claim 中途崩溃 10min 假 duplicate | routes + idempotency |
| **MCP-R3-1** | 干净 WS 关闭重连 delay 重置 1s（风暴） | `mcp_pipe.py` |
| **RT-R3-6** | 音频 clip 无限流 | `device_app_chat.py` |
| **RT-R3-7** | status WS 终端事件同步 SQLite | `device_app_status_ws.py` |

---

## 🟡 Suggestion

- GW-R3-13 截断 path 不在笔画边界
- GW-R3-14 memory/redis recover-ack 语义分叉
- GW-R3-15 `FAMILY_ALLOWLISTS.motion` 缺 `estop`/`handwriting`（潜伏）
- RT-R3-8 batch-tasks 预扣限流槽
- VO-R3-2 voice WS 鉴权同步 SQLite
- MCP-R3-2 duplicate 无 task_id
- CORE-Y8 `/dlc/tasks/validate` 仍无限流（有 HARD_MAX=5000 点，CPU 轻但面仍在）
- chat-web FE-8：`html.replace(key, rendered)` 若 key 含 `$` 特殊替换语义（低）

---

## 本轮确认已修（勿再当 open）

| 原 ID | 状态 |
|-------|------|
| GW-B1 / GW-B2 | text/svg normalize + 退化 span；残差见 R3-7 multipass |
| CORE-O4（dlc_core） | 固定；**gateway profile 路径见 R3-3** |
| GW-WA / GW-WB | coordinator run_path；restart 离线诚实失败 |
| GW-WH | 急停优先 + 未知拒动；残差 LLM R3-8 |
| GW-WC 主路径 | dispatch_gen 存在；残差无 gen ack R3-2 |
| GW-WG | expire_stale_queued 挂 busy 查询；TTL 1h 仍长 R3-9 |
| RT-W1 无限流 | 有限流；残差顺序 R3-1 |
| RT-W2 无限流 | RPM+SVG 大小；残差 N 扇出 R3-2 |
| CORE-O1 / O2 / O3 | 友好 duplicate；子进程退避；status to_thread |
| FE-1 / 流式切会话 / async image DNS | 已合 `4b923cbb` 等 |
| FW-F1 / F3（代码） | STOP 实时字节 + string msg_id；**HIL 未做** |

---

## 优先级建议（物理安全优先）

1. **GW-R3-1** NaN feed
2. **GW-R3-3 + GW-R3-5** profile NaN + 无 profile 越界
3. **GW-R3-4** pop 重验 path
4. **GW-R3-2** gen-less ack
5. **RT-R3-1** 模板 insert-first
6. **GW-R3-6 / R3-7 / GW-WF** 手写 fail-open、multipass、SVG 隐式坐标
7. **RT-R3-2/3/4/5 + VO-R3-1** 限流与 ticket
8. **CORE/MCP 事件循环与重连**

---

## 复现脚本（只读）

```python
import math
from device_gateway.path_validator import validate_run_path_params, validate_capability_params
from device_intelligence.safety import profile_limit_error
from types import SimpleNamespace
from device_gateway.svg_parser import svg_path_to_motion

s, e = validate_run_path_params({"path":[{"x":1,"y":1,"z":0}], "feed": float("nan")})
assert e is None and math.isnan(s["feed"])  # GW-R3-1

p = SimpleNamespace(workspace_mm={"x": float("nan"), "y": 100, "z": 20}, max_feed=1200, max_path_points=200)
assert profile_limit_error({"path":[{"x":999,"y":0,"z":0}], "feed":100}, p) is None  # GW-R3-3

s2, e2 = validate_capability_params("run_path", {"path":[{"x":400,"y":0,"z":0}], "feed":500})
assert e2 is None  # GW-R3-5

assert len(svg_path_to_motion("M0 0 L 10 0 20 10 30 0")) == 2  # GW-WF should be 4
```

---

## 建议下一步

- **默认**：立任务修 Blocker 6 项（可一域 B 并行：validator + redis gate + template order）。
- **不建议**：再开四域慢复审；本报告已覆盖未完成的 #2/#3。
- **真机仍挂**：FW 急停 HIL、WDT HIL、`07-20-u8-wdt-panic-hil`。

---

## 修复状态（2026-07-20 follow-up）

| ID | 状态 | 要点 |
|----|------|------|
| GW-R3-1 | **已修** | `validate_run_path_params` 拒 NaN/Inf feed |
| GW-R3-3 | **已修** | workspace 归一化 + `profile_limit_error` 拒非有限工作区 |
| GW-R3-5 | **已修（修正）** | 无 profile 预检回落 ±500 硬限（真实固件 300×300×80mm，初版 100mm 硬拒合法坐标）；`[0, workspace]` 仍由 profile 解析后 `profile_limit_error` 强制 |
| GW-R3-2 | **已修（门控）** | strict 拒 gen-less ack 由 `LIMA_STRICT_DISPATCH_GEN` 门控，默认关闭；固件回带 `dispatch_gen`（B5）前开启会让每个 recovered 任务死循环 |
| GW-R3-4 | **已修** | SEC-06 `validate_task_schema` 重跑 `validate_capability_params` |
| GW-R3-7 | **已修** | render_text/svg 在 multi_pass/optimizer 之后复检工作区边界（`_assert_path_within_workspace`）；normalize-time 断言只在 +X 平移前跑，多道 offset 可越界后静默下发 |
| GW-R3-6 | **已修** | 手写 bounds 预检异常改 fail-closed（返回错误串），对齐 `device_draw_handler`，不再 `return None` 当作通过 |
| GW-R3-10 | **已修** | `task_draw_params._clamp_feed` 加 `math.isfinite`，NaN/Inf 回落 default 而非静默钳到 MAX_FEED 2000（> 1200 安全上限） |
| GW-R3-8 | **已修（并入 R3-12）** | LLM replan 守卫收窄为 `_REPLAN_BLOCKED_CAPABILITIES`（画类）；`rejected` 不可改写成 run_path/write_text/draw，但**可**改写成 move / 控制类 |
| GW-R3-12 | **已修（接通）** | move_abs/move_rel 全链路接通：四处 allowlist + `CAPABILITY_PATH_MAP` + `_validate_move_params`（move_abs 服务端 [0,workspace]/±500 校验、move_rel ±1mm jog）+ 投影层 passthrough（不再改写成 run_path）+ 语音模糊控制放行；不需审批直接下发 |
| RT-R3-1 | **已修** | 模板 execute insert → dispatch → 失败 mark_task_failed |

回归：`tests/test_review_round3_blockers.py`、`tests/test_move_capability_e2e.py` + 既有 redis/path_validator/template/intent 套件。
