# 路由权威 bypass 审计与收敛计划

**日期：** 2026-06-13
**触发：** LiMa Multi-CLI 项目级审查 fix-pack P1（A4）
**权威文档：** `docs/REQUEST_PIPELINE_AUTHORITY.md` — `routing_engine.route()` 为 chat/coding 唯一路由入口

## 1. 审计结论（生产路径）

| # | 文件 | 行号 | 调用 | 分类 | 状态 |
|---|------|------|------|------|------|
| 1 | `routes/v3_adapters.py` | 20–23 | `routing_engine.route()` | ✅ 合规 | — |
| 2 | `routes/v3_adapters.py` | — | `routing_engine.select()` | ⚠️ bypass | ✅ Phase 2 已关闭 |
| 3 | `routes/v3_adapters.py` | — | `routing_engine.select()` | ⚠️ bypass | ✅ Phase 2 已关闭 |
| 4 | `routes/v3_adapters.py` | — | `inject_retrieval_context()` | ⚠️ 部分 bypass | ✅ Phase 2 已关闭 |
| 5 | `routes/v3_adapters.py` | — | `classify_scenario()` | ⚠️ 部分 bypass | ✅ Phase 2 已关闭 |
| 6 | `routes/chat_stream.py` | — | `select()` + `execute()` | 🔴 bypass | ✅ Phase 1 已关闭 |
| 7 | `routes/stream_handlers.py` | 45–46 | `v3_predict` / `v3_select` | ⚠️ 间接 bypass | ✅ Phase 2 已关闭 |

**Qoder scout 补充（2026-06-13，同 scope `routes/`）：**

| # | 文件 | 严重度 | 问题 | 状态 |
|---|------|--------|------|------|
| 8 | `routes/chat_support.py` | P0 | `thinking_route` 直调 `router_http.call_api` | ✅ Phase 1 已关闭 |
| 9 | `routes/chat_handler_dispatch.py` | P0 | `orchestrate()` 非流式路径跳过 `route()` | ✅ Phase 1 已关闭 |
| 10 | `routes/chat_stream.py` | P0 | `orchestrate()` 流式路径跳过 `route()` | ✅ Phase 1 已关闭 |
| 11 | `routes/eval_internal.py` | P1 | eval 直调 `http_caller`，无 health/budget | 待 Phase 3+ |
| 12 | `routes/token_sync.py` | P1 | urllib + 裸 `except Exception: return False` | ✅ Phase 2.5 校验收紧 + warning 日志 |

完整 JSON：`.omc/artifacts/lima-multi-cli/findings.json`（18 条，Qoder lane）。

**合规引用（非 bypass）：**

- `orchestrate.py`、`channel_gateway/*` → `routing_engine.route()`
- `routes/chat_handler_dispatch.py` 非流式 → `v3_route` → `route()`
- `tests/*` 对 `select`/`route` 的单测 — 允许

**当前无静态测试** 禁止 `routes/` 内 `routing_engine.select|execute` 直调（`test_routing_pipeline_authority.py` 仅测模块源码，未扫 routes）。

## 2. 根因

1. **流式路径历史包袱：** `v3_predict` / `v3_select` 为低延迟 speculative streaming 定制，内含硬编码 backend 列表与 `classify_scenario` 直调。
2. **chat_stream 兜底：** speculative 无输出时手写 `select` + `execute`，未复用 `route()` 的 identity、skills、validator、post-process。
3. **公开 API 泄漏：** `routing_engine.select` / `execute` 作为模块级函数可被 routes 直接 import 调用，权威边界仅靠文档约束。

## 3. 收敛策略（渐进，可回滚）

### Phase 0 — 门禁（本里程碑）

- [x] 新增 `tests/test_routing_pipeline_authority.py::TestRoutesBypassGuard`（allowlist 已清空，Phase 2 后归零）
- [x] 文档 SSOT：本文档 + `REQUEST_PIPELINE_AUTHORITY.md` 增加「已知 bypass 表」链接

### Phase 1 — chat_stream 兜底（P1，热路径） ✅ 2026-06-13

**已完成：** speculative 失败回退、`orchestrate` 分支统一经 `_authoritative_route()` → `v3_route` / `orchestrate(..., messages=, ide_source=, system_prompt=)`。

**已完成（P0 部分）：**

- `chat_handler_dispatch` / `orchestrate()` 传入完整 preflight 上下文
- `thinking_route` 改用 `http_caller` + `routing_executor.execute`（移除 `router_http`）

**方案 A（推荐）：** 回退改为 `asyncio.to_thread(v3_route, ...)`，与非流式一致。
**方案 B：** 新增 `routing_engine.route_stream()` facade，内部复用 route 前半段 + 流式 execute。

**验收：**

- `grep routing_engine\.select routes/chat_stream.py` 无匹配
- `tests/test_chat_stream*.py` 或现有 chat 流式测试 green

### Phase 2 — v3_predict / v3_select（P1，流式 speculative） ✅ 2026-06-13

**已完成：** 新增 `routing_engine.pick_backend()`（与 `route()` 共享 classify/inject/select/skills 管线）；`v3_predict` / `v3_select` 委托 `pick_backend`，移除硬编码 backend 列表与 `routing_engine.select()` 回退；`TestRoutesBypassGuard` allowlist 清空。

### Phase 2.5 — 流式选路一致性 P0 ✅ 2026-06-13

**设计文档：** [`2026-06-13-stream-routing-consistency-p0-design.md`](2026-06-13-stream-routing-consistency-p0-design.md)

**已完成：** speculative 透传 `system_prompt`；`_pick_for_stream` 对齐 predict/select；`token_sync` 仅 2xx+有效 content 接受 override。

### Phase 3 — 模块边界（P2）

- `routing_engine` 考虑将 `select`/`execute` 改为 `_select`/`_execute` 或移入 `routing_engine/_internal.py`，仅 `route` 公开
- 超大文件拆分见 CQ 计划（`routing_engine.py`、`xiaozhi_v1_compat.py` 等）

## 4. routes/ 超标文件（本地 wc，2026-06-13）

| 文件 | 行数 | 备注 |
|------|-----:|------|
| `xiaozhi_v1_compat.py` | 432 | 超 AGENTS.md 300 行红线 |
| `admin_api_extra.py` | 377 | 同上 |
| `chat_endpoints.py` | 310 | 同上 |
| `routing_engine.py` | 287 | 模块级 OK，但 `route()` 函数体仍过大 |

## 5. 验收清单

```powershell
# bypass 归零（Phase 1+2 完成后）
rg "routing_engine\.(select|execute)\(" routes/

# 权威测试
python -m pytest tests/test_routing_pipeline_authority.py tests/test_routing_engine.py -q

# multi-cli verify（可选）
python .claude/skills/lima-multi-cli/driver.py verify --task "routing authority bypass closed"
```

## 6. 非目标

- 不修改 `device_gateway/` 路由（已与 chat 路由隔离，见现有 authority 测试）
- 不在本计划内重写 speculative streaming 算法，仅收敛入口
